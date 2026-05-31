from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands


APPLICATION_TIMEOUT_SECONDS = max(300, int(os.getenv("APPLICATION_TIMEOUT_SECONDS", "10800")))
APPLICATION_START_TIMEOUT_SECONDS = max(60, min(900, APPLICATION_TIMEOUT_SECONDS))
DEFAULT_PANEL_TEXT = "Select an option to begin!"
FORM_NAME_RE = re.compile(r"[^a-z0-9]+")
STATE_FILE = ""
STATE_DIR = ""
STATE: Dict[str, Any] = {"guilds": {}}
BOT: Optional[commands.Bot] = None
REGISTERED = False
VIEWS_RESTORED = False
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}


def utc_now() -> int:
    return int(time.time())


def normalize_panel_key(name: str) -> str:
    key = FORM_NAME_RE.sub("-", str(name or "").strip().lower()).strip("-")
    return key[:64]


def stable_suffix(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def truncate(value: Any, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_user(user_id: int) -> str:
    return f"<@{user_id}> (`{user_id}`)"


def bot_channel_permission_errors(channel: discord.TextChannel) -> list[str]:
    if BOT is None or BOT.user is None:
        return ["bot is not ready"]
    bot_member = channel.guild.me or channel.guild.get_member(BOT.user.id)
    if bot_member is None:
        return ["bot member could not be resolved"]
    permissions = channel.permissions_for(bot_member)
    checks = (
        ("View Channel", permissions.view_channel),
        ("Send Messages", permissions.send_messages),
        ("Embed Links", permissions.embed_links),
        ("Read Message History", permissions.read_message_history),
    )
    return [name for name, allowed in checks if not allowed]


def prune_application_sessions(user_id: Optional[int] = None) -> int:
    now = utc_now()
    removed = 0
    for session_id, session in list(ACTIVE_SESSIONS.items()):
        if user_id is not None and int(session.get("user_id") or 0) != int(user_id):
            continue
        created_at = int(session.get("created_at") or now)
        start_timeout = not session.get("started") and now - created_at >= APPLICATION_START_TIMEOUT_SECONDS
        full_timeout = now - created_at >= APPLICATION_TIMEOUT_SECONDS
        if start_timeout or full_timeout:
            ACTIVE_SESSIONS.pop(session_id, None)
            removed += 1
    return removed


def cleanup_application_task(session_id: str, task: asyncio.Task) -> None:
    try:
        error = task.exception()
    except asyncio.CancelledError:
        error = None
    if error:
        print(f"Application session {session_id} crashed: {error}")
    ACTIVE_SESSIONS.pop(session_id, None)


def default_state() -> Dict[str, Any]:
    return {"guilds": {}}


def validate_state(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return default_state()
    guilds = data.get("guilds")
    if not isinstance(guilds, dict):
        data["guilds"] = {}
    return data


def validate_guild_state(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    data.setdefault("panel_text", DEFAULT_PANEL_TEXT)
    panels = data.get("panels")
    if not isinstance(panels, dict):
        data["panels"] = {}
    submissions = data.get("submissions")
    if not isinstance(submissions, dict):
        data["submissions"] = {}
    return data


def read_state_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return validate_state(json.load(handle))


def read_guild_state_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return validate_guild_state(json.load(handle))


def write_json_with_backup(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    backup_path = f"{path}.bak"
    if os.path.exists(path):
        try:
            shutil.copy2(path, backup_path)
        except OSError as error:
            print(f"Failed to refresh backup {backup_path}: {error}")
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temp_path, path)


def load_state() -> Dict[str, Any]:
    if not STATE_FILE and not STATE_DIR:
        return default_state()

    loaded_from_legacy = False
    data = default_state()
    backup_path = f"{STATE_FILE}.bak"
    if STATE_FILE:
        try:
            data = read_state_file(STATE_FILE)
            loaded_from_legacy = True
        except FileNotFoundError:
            try:
                data = read_state_file(backup_path)
                loaded_from_legacy = True
            except FileNotFoundError:
                data = default_state()
            except Exception as error:
                print(f"Failed to load backup application state {backup_path}: {error}")
                data = default_state()
        except Exception as error:
            print(f"Failed to load {STATE_FILE}: {error}")
            try:
                data = read_state_file(backup_path)
                loaded_from_legacy = True
            except Exception as backup_error:
                print(f"Failed to load backup application state {backup_path}: {backup_error}")
                data = default_state()
            else:
                print(f"Recovered application state from backup {backup_path}.")

    data = validate_state(data)

    if STATE_DIR and os.path.isdir(STATE_DIR):
        for entry in os.scandir(STATE_DIR):
            if not entry.is_file() or not entry.name.endswith(".json"):
                continue
            guild_id = entry.name[:-5]
            if not guild_id.isdigit():
                continue
            try:
                data["guilds"][guild_id] = read_guild_state_file(entry.path)
            except Exception as error:
                backup_file = f"{entry.path}.bak"
                try:
                    data["guilds"][guild_id] = read_guild_state_file(backup_file)
                except Exception as backup_error:
                    print(f"Failed to load application state for guild {guild_id}: {error}; backup failed: {backup_error}")
                else:
                    print(f"Recovered application state for guild {guild_id} from backup.")

    if loaded_from_legacy and STATE_DIR:
        print("Loaded legacy application state; it will be migrated into per-server files on save.")
    return data


def save_state() -> None:
    if STATE_DIR:
        for guild_id, guild_state in validate_state(STATE).get("guilds", {}).items():
            safe_guild_id = re.sub(r"[^0-9]", "", str(guild_id))
            if not safe_guild_id:
                continue
            write_json_with_backup(os.path.join(STATE_DIR, f"{safe_guild_id}.json"), validate_guild_state(guild_state))
        return
    if STATE_FILE:
        write_json_with_backup(STATE_FILE, validate_state(STATE))


def get_guild_state(guild_id: int) -> Dict[str, Any]:
    guilds = STATE.setdefault("guilds", {})
    guild_state = guilds.setdefault(str(guild_id), {})
    guild_state.setdefault("panel_text", DEFAULT_PANEL_TEXT)
    guild_state.setdefault("panels", {})
    guild_state.setdefault("submissions", {})
    return guild_state


def get_panel(guild_id: int, panel_key: str) -> Optional[Dict[str, Any]]:
    return get_guild_state(guild_id).get("panels", {}).get(panel_key)


def get_submission(guild_id: int, submission_id: str) -> Optional[Dict[str, Any]]:
    return get_guild_state(guild_id).get("submissions", {}).get(submission_id)


def has_application_admin(interaction: discord.Interaction) -> bool:
    return isinstance(interaction.user, discord.Member) and (
        interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator
    )


async def require_application_admin(interaction: discord.Interaction) -> bool:
    if has_application_admin(interaction):
        return True
    await interaction.response.send_message(
        "You need Manage Server permission to manage applications.",
        ephemeral=True,
    )
    return False


async def panel_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        return []
    panels = get_guild_state(interaction.guild_id).get("panels", {})
    needle = current.lower().strip()
    choices: list[app_commands.Choice[str]] = []
    for panel_key, panel in sorted(panels.items()):
        display_name = panel.get("name", panel_key)
        if needle and needle not in panel_key and needle not in display_name.lower():
            continue
        choices.append(app_commands.Choice(name=truncate(display_name, 100), value=panel_key))
        if len(choices) >= 25:
            break
    return choices


async def resolve_text_channel(guild: discord.Guild, channel_id: int) -> Optional[discord.TextChannel]:
    channel = guild.get_channel(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
    return channel if isinstance(channel, discord.TextChannel) else None


def panel_questions(panel: Dict[str, Any]) -> list[str]:
    questions = panel.get("questions")
    if not isinstance(questions, list):
        return []
    return [str(question).strip() for question in questions if str(question).strip()]


def build_application_panel_embed(guild: discord.Guild) -> discord.Embed:
    guild_state = get_guild_state(guild.id)
    embed = discord.Embed(
        title="Applications",
        description=guild_state.get("panel_text") or DEFAULT_PANEL_TEXT,
        color=discord.Color.blue(),
    )
    embed.set_author(name="Application bot")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


def build_question_embed(panel: Dict[str, Any], index: int, total: int, question: str) -> discord.Embed:
    title = panel.get("name", "Application")
    if not title.lower().endswith("application"):
        title = f"{title} Application"
    embed = discord.Embed(
        title=truncate(title, 256),
        description=f"**{index}/{total}. {question}**",
        color=discord.Color.blue(),
    )
    embed.set_footer(text="To answer this question, please send a message to the bot with your response.")
    return embed


def build_submission_embed(guild: discord.Guild, panel: Dict[str, Any], submission: Dict[str, Any]) -> discord.Embed:
    status = submission.get("status", "pending")
    color = {
        "accepted": discord.Color.green(),
        "denied": discord.Color.red(),
    }.get(status, discord.Color.orange())

    title = f"{submission.get('username', 'Unknown')}'s '{panel.get('name', 'Application')}' Application"
    embed = discord.Embed(
        title=truncate(title, 256),
        description=f"**{status.title()}**",
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    if submission.get("avatar_url"):
        embed.set_thumbnail(url=submission["avatar_url"])

    answers = submission.get("answers", [])
    for index, answer in enumerate(answers[:20], start=1):
        embed.add_field(
            name=f"{index}. {truncate(answer.get('question', 'Question'), 256)}",
            value=truncate(answer.get("answer", "No answer"), 950) or "No answer",
            inline=False,
        )

    if len(answers) > 20:
        embed.add_field(
            name="More answers",
            value="This application has more than 20 answers. The full data is saved in the application data file.",
            inline=False,
        )

    stats = [
        f"UserId: `{submission['user_id']}`",
        f"Username: `{submission.get('username', 'unknown')}`",
        f"User: <@{submission['user_id']}>",
        f"Duration: `{format_duration(int(submission.get('duration_seconds') or 0))}`",
        f"Submitted: <t:{int(submission.get('created_at', utc_now()))}:R>",
    ]
    if submission.get("reviewer_id"):
        stats.append(f"Reviewer: <@{submission['reviewer_id']}>")
    if submission.get("reason"):
        stats.append(f"Reason: {truncate(submission['reason'], 500)}")
    embed.add_field(name="Submission stats", value="\n".join(stats), inline=False)
    embed.set_footer(text=f"Submission {submission['id']}")
    return embed


async def send_applicant_dm(user_id: int, *, content: Optional[str] = None, embed: Optional[discord.Embed] = None) -> None:
    if BOT is None:
        return
    try:
        user = BOT.get_user(user_id) or await BOT.fetch_user(user_id)
    except discord.HTTPException:
        return
    try:
        await user.send(content=content, embed=embed)
    except discord.HTTPException:
        pass


async def post_application_log(guild: discord.Guild, panel: Dict[str, Any], submission: Dict[str, Any], text: str) -> bool:
    guild_state = get_guild_state(guild.id)
    channel_id = int(guild_state.get("log_channel_id") or 0)
    if not channel_id:
        print(f"Application log skipped for guild {guild.id}: no log channel configured.")
        return False
    channel = await resolve_text_channel(guild, channel_id)
    if not channel:
        print(f"Application log skipped for guild {guild.id}: channel {channel_id} was not found.")
        return False
    missing_permissions = bot_channel_permission_errors(channel)
    if missing_permissions:
        print(
            f"Application log skipped for guild {guild.id}: missing permissions in "
            f"#{channel.name}: {', '.join(missing_permissions)}"
        )
        return False
    embed = discord.Embed(
        title="Application log",
        description=text,
        color=discord.Color.dark_teal(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Applicant", value=format_user(int(submission["user_id"])), inline=False)
    embed.add_field(name="Panel", value=panel.get("name", submission.get("panel_key", "application")), inline=True)
    embed.add_field(name="Status", value=str(submission.get("status", "pending")).title(), inline=True)
    try:
        await channel.send(embed=embed)
        return True
    except discord.HTTPException as error:
        print(f"Application log failed for guild {guild.id} in channel {channel.id}: {error}")
        return False


async def post_or_update_submission(guild: discord.Guild, panel: Dict[str, Any], submission: Dict[str, Any]) -> bool:
    guild_state = get_guild_state(guild.id)
    log_channel_id = int(guild_state.get("log_channel_id") or 0)
    if not log_channel_id:
        print(f"Application submission skipped for guild {guild.id}: no log channel configured.")
        return False
    channel = await resolve_text_channel(guild, log_channel_id)
    if not channel:
        print(f"Application submission skipped for guild {guild.id}: channel {log_channel_id} was not found.")
        return False
    missing_permissions = bot_channel_permission_errors(channel)
    if missing_permissions:
        print(
            f"Application submission skipped for guild {guild.id}: missing permissions in "
            f"#{channel.name}: {', '.join(missing_permissions)}"
        )
        return False

    embed = build_submission_embed(guild, panel, submission)
    view = ApplicationReviewView(guild.id, submission["id"], disabled=submission.get("status") != "pending")

    if submission.get("review_message_id"):
        try:
            message = await channel.fetch_message(int(submission["review_message_id"]))
            await message.edit(embed=embed, view=view)
            return True
        except discord.HTTPException as error:
            print(f"Application submission update failed for guild {guild.id}: {error}")
            pass

    try:
        message = await channel.send(embed=embed, view=view)
    except discord.HTTPException as error:
        print(f"Application submission send failed for guild {guild.id} in channel {channel.id}: {error}")
        return False
    else:
        submission["review_channel_id"] = channel.id
        submission["review_message_id"] = message.id
        save_state()
        return True


async def refresh_application_message(guild: discord.Guild) -> bool:
    guild_state = get_guild_state(guild.id)
    channel_id = int(guild_state.get("application_channel_id") or 0)
    message_id = int(guild_state.get("application_message_id") or 0)
    if not channel_id or not message_id:
        return False

    channel = await resolve_text_channel(guild, channel_id)
    if not channel:
        return False

    try:
        message = await channel.fetch_message(message_id)
        await message.edit(embed=build_application_panel_embed(guild), view=ApplicationSelectView(guild.id))
        return True
    except discord.HTTPException:
        return False


class ApplicationSelect(discord.ui.Select):
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        options: list[discord.SelectOption] = []
        panels = get_guild_state(guild_id).get("panels", {})
        for panel_key, panel in sorted(panels.items()):
            if panel.get("enabled", True) is False:
                continue
            options.append(
                discord.SelectOption(
                    label=truncate(panel.get("name", panel_key), 100),
                    description=truncate(panel.get("description", "Start this application."), 100),
                    value=panel_key,
                )
            )
            if len(options) >= 25:
                break
        if not options:
            options = [
                discord.SelectOption(
                    label="No applications open",
                    description="Staff can create panels with /createpanel.",
                    value="__none__",
                )
            ]

        super().__init__(
            placeholder="Make a selection",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"dexapp:select:{guild_id}",
            disabled=options[0].value == "__none__",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id != self.guild_id:
            await interaction.response.send_message("This application panel belongs to another server.", ephemeral=True)
            return
        await start_application_from_interaction(interaction, self.values[0])


class ApplicationSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.add_item(ApplicationSelect(guild_id))


class ApplicationStartView(discord.ui.View):
    def __init__(self, session_id: str):
        super().__init__(timeout=APPLICATION_TIMEOUT_SECONDS)
        self.session_id = session_id

        start_button = discord.ui.Button(
            label="Start application",
            style=discord.ButtonStyle.success,
            custom_id=f"dexapp:start:{session_id}",
        )
        cancel_button = discord.ui.Button(
            label="Cancel application",
            style=discord.ButtonStyle.danger,
            custom_id=f"dexapp:cancel:{session_id}",
        )
        start_button.callback = self.start_button
        cancel_button.callback = self.cancel_button
        self.add_item(start_button)
        self.add_item(cancel_button)

    async def start_button(self, interaction: discord.Interaction) -> None:
        session = ACTIVE_SESSIONS.get(self.session_id)
        if not session or interaction.user.id != session["user_id"]:
            await interaction.response.send_message("This application session is not yours.", ephemeral=True)
            return
        if session.get("started"):
            await interaction.response.send_message("This application already started.", ephemeral=True)
            return
        session["started"] = True
        await interaction.response.edit_message(view=None)
        task = asyncio.create_task(run_application_session(self.session_id))
        task.add_done_callback(lambda done_task: cleanup_application_task(self.session_id, done_task))

    async def cancel_button(self, interaction: discord.Interaction) -> None:
        session = ACTIVE_SESSIONS.pop(self.session_id, None)
        if not session or interaction.user.id != session["user_id"]:
            await interaction.response.send_message("This application session is not yours.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="Application cancelled",
                description="Your application was cancelled.",
                color=discord.Color.red(),
            ),
            view=None,
        )


class ReviewReasonModal(discord.ui.Modal):
    def __init__(self, guild_id: int, submission_id: str, status: str):
        super().__init__(title=f"{status.title()} with reason")
        self.guild_id = guild_id
        self.submission_id = submission_id
        self.status = status
        self.reason = discord.ui.TextInput(
            label="Reason",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000,
            placeholder="Tell the applicant why.",
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await handle_review(interaction, self.guild_id, self.submission_id, self.status, str(self.reason.value).strip())


class ApplicationReviewView(discord.ui.View):
    def __init__(self, guild_id: int, submission_id: str, *, disabled: bool = False):
        super().__init__(timeout=None)
        buttons = [
            ("Accept", discord.ButtonStyle.success, "accepted", None),
            ("Deny", discord.ButtonStyle.danger, "denied", None),
            ("Accept with reason", discord.ButtonStyle.success, "accepted", "reason"),
            ("Deny with reason", discord.ButtonStyle.danger, "denied", "reason"),
            ("History", discord.ButtonStyle.primary, "history", None),
        ]
        for label, style, action, mode in buttons:
            button = discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"dexapp:review:{stable_suffix(label)}:{guild_id}:{submission_id}",
                disabled=disabled and action != "history",
            )
            if action == "history":
                button.callback = self.history_button(guild_id, submission_id)
            elif mode == "reason":
                button.callback = self.reason_button(guild_id, submission_id, action)
            else:
                button.callback = self.review_button(guild_id, submission_id, action)
            self.add_item(button)

    def review_button(self, guild_id: int, submission_id: str, status: str):
        async def callback(interaction: discord.Interaction) -> None:
            await handle_review(interaction, guild_id, submission_id, status, None)

        return callback

    def reason_button(self, guild_id: int, submission_id: str, status: str):
        async def callback(interaction: discord.Interaction) -> None:
            await interaction.response.send_modal(ReviewReasonModal(guild_id, submission_id, status))

        return callback

    def history_button(self, guild_id: int, submission_id: str):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.guild_id != guild_id:
                await interaction.response.send_message("This review belongs to another server.", ephemeral=True)
                return
            if not await require_application_admin(interaction):
                return
            submission = get_submission(guild_id, submission_id)
            if not submission:
                await interaction.response.send_message("That submission no longer exists.", ephemeral=True)
                return
            await send_application_history(interaction, int(submission["user_id"]))

        return callback


async def start_application_from_interaction(interaction: discord.Interaction, panel_key: str) -> None:
    if BOT is None:
        await interaction.response.send_message("Application system is not ready.", ephemeral=True)
        return
    if not interaction.guild or not interaction.guild_id:
        await interaction.response.send_message("Use this inside a server.", ephemeral=True)
        return

    panel_key = normalize_panel_key(panel_key)
    panel = get_panel(interaction.guild_id, panel_key)
    if not panel or panel.get("enabled", True) is False:
        await interaction.response.send_message("That application is not open.", ephemeral=True)
        return

    questions = panel_questions(panel)
    if not questions:
        await interaction.response.send_message("This application has no questions yet.", ephemeral=True)
        return

    prune_application_sessions(interaction.user.id)
    if any(int(session.get("user_id") or 0) == interaction.user.id for session in ACTIVE_SESSIONS.values()):
        await interaction.response.send_message("You already have an application open in DMs.", ephemeral=True)
        return

    try:
        dm_channel = await interaction.user.create_dm()
    except discord.HTTPException:
        await interaction.response.send_message("I could not DM you. Open your DMs and try again.", ephemeral=True)
        return

    session_id = uuid.uuid4().hex[:12]
    ACTIVE_SESSIONS[session_id] = {
        "id": session_id,
        "guild_id": interaction.guild_id,
        "panel_key": panel_key,
        "user_id": interaction.user.id,
        "dm_channel_id": dm_channel.id,
        "created_at": utc_now(),
        "started": False,
    }

    confirm = discord.Embed(
        title=panel.get("name", "Application"),
        description=(
            "Are you sure you want to apply?\n\n"
            f"Once you start, I will send you **{len(questions)}** questions. "
            f"You have **{format_duration(APPLICATION_TIMEOUT_SECONDS)}** to finish. "
            "You can type `cancel` at any time."
        ),
        color=discord.Color.blue(),
    )
    dm_message = await dm_channel.send(embed=confirm, view=ApplicationStartView(session_id))

    started_embed = discord.Embed(
        title="Application started",
        description="Application has been started in your direct messages!",
        color=discord.Color.green(),
    )
    jump = discord.ui.View()
    jump.add_item(discord.ui.Button(label="Jump to application", url=dm_message.jump_url))
    await interaction.response.send_message(embed=started_embed, view=jump, ephemeral=True)


async def run_application_session(session_id: str) -> None:
    if BOT is None:
        return
    session = ACTIVE_SESSIONS.get(session_id)
    if not session:
        return

    guild_id = int(session["guild_id"])
    user_id = int(session["user_id"])
    panel = get_panel(guild_id, session["panel_key"])
    guild = BOT.get_guild(guild_id)
    if not guild or not panel:
        ACTIVE_SESSIONS.pop(session_id, None)
        return

    try:
        user = BOT.get_user(user_id) or await BOT.fetch_user(user_id)
        dm_channel = user.dm_channel or await user.create_dm()
    except discord.HTTPException:
        ACTIVE_SESSIONS.pop(session_id, None)
        return

    questions = panel_questions(panel)
    await dm_channel.send(
        embed=discord.Embed(
            title="Application Started",
            description="Please answer the questions below, either by clicking dropdown menus or sending a message to the bot.",
            color=discord.Color.green(),
        )
    )

    start_time = utc_now()
    deadline = int(session.get("created_at", start_time)) + APPLICATION_TIMEOUT_SECONDS
    answers = []

    for index, question in enumerate(questions, start=1):
        remaining_time = max(0, deadline - utc_now())
        if remaining_time <= 0:
            await dm_channel.send(
                embed=discord.Embed(
                    title="Application expired",
                    description="You did not complete the application in time.",
                    color=discord.Color.red(),
                )
            )
            ACTIVE_SESSIONS.pop(session_id, None)
            return

        await dm_channel.send(embed=build_question_embed(panel, index, len(questions), question))

        def check(message: discord.Message) -> bool:
            return (
                message.author.id == user_id
                and message.channel.id == dm_channel.id
                and not message.author.bot
            )

        try:
            message = await BOT.wait_for("message", check=check, timeout=remaining_time)
        except asyncio.TimeoutError:
            await dm_channel.send(
                embed=discord.Embed(
                    title="Application expired",
                    description="You did not complete the application in time.",
                    color=discord.Color.red(),
                )
            )
            ACTIVE_SESSIONS.pop(session_id, None)
            return

        answer = message.content.strip()
        if answer.lower() in {"cancel", "stop"}:
            await dm_channel.send(
                embed=discord.Embed(
                    title="Application cancelled",
                    description="Your application was cancelled.",
                    color=discord.Color.red(),
                )
            )
            ACTIVE_SESSIONS.pop(session_id, None)
            return

        answers.append({"question": question, "answer": answer or "No answer"})

    member = guild.get_member(user_id)
    username = str(member or user)
    avatar_url = (member.display_avatar.url if member else user.display_avatar.url)
    submission_id = uuid.uuid4().hex[:10]
    submission = {
        "id": submission_id,
        "panel_key": session["panel_key"],
        "user_id": user_id,
        "username": username,
        "avatar_url": avatar_url,
        "answers": answers,
        "status": "pending",
        "created_at": utc_now(),
        "duration_seconds": utc_now() - start_time,
    }
    get_guild_state(guild_id)["submissions"][submission_id] = submission
    save_state()
    ACTIVE_SESSIONS.pop(session_id, None)

    await dm_channel.send(
        embed=discord.Embed(
            title="Application submitted.",
            description="Your application has been submitted.",
            color=discord.Color.green(),
        )
    )
    posted_review = await post_or_update_submission(guild, panel, submission)
    posted_log = await post_application_log(guild, panel, submission, "A new application was submitted.")
    if not posted_review and not posted_log:
        await dm_channel.send(
            embed=discord.Embed(
                title="Application log warning",
                description=(
                    "Your application was saved, but I could not post it to the server log channel. "
                    "Please tell a server admin to run `/applicationlog` again in a channel where I can send embeds."
                ),
                color=discord.Color.orange(),
            )
        )


async def handle_review(
    interaction: discord.Interaction,
    guild_id: int,
    submission_id: str,
    status: str,
    reason: Optional[str],
) -> None:
    if not interaction.guild or interaction.guild_id != guild_id:
        await interaction.response.send_message("This review belongs to another server.", ephemeral=True)
        return
    if not await require_application_admin(interaction):
        return

    submission = get_submission(guild_id, submission_id)
    if not submission:
        await interaction.response.send_message("That submission no longer exists.", ephemeral=True)
        return
    if submission.get("status") != "pending":
        await interaction.response.send_message("This application was already reviewed.", ephemeral=True)
        return

    panel = get_panel(guild_id, submission.get("panel_key", ""))
    if not panel:
        await interaction.response.send_message("The panel for this submission no longer exists.", ephemeral=True)
        return

    submission["status"] = status
    submission["reason"] = reason or ""
    submission["reviewer_id"] = interaction.user.id
    submission["reviewed_at"] = utc_now()
    save_state()

    embed = build_submission_embed(interaction.guild, panel, submission)
    disabled_view = ApplicationReviewView(guild_id, submission_id, disabled=True)
    if interaction.message:
        await interaction.response.edit_message(embed=embed, view=disabled_view)
    else:
        await post_or_update_submission(interaction.guild, panel, submission)
        await interaction.response.send_message(f"Application {status}.", ephemeral=True)

    applicant_embed = discord.Embed(
        title=f"Application {status}",
        description=f"Your **{panel.get('name', 'application')}** application in **{interaction.guild.name}** was **{status}**.",
        color=discord.Color.green() if status == "accepted" else discord.Color.red(),
    )
    if reason:
        applicant_embed.add_field(name="Reason", value=truncate(reason, 1000), inline=False)
    await send_applicant_dm(int(submission["user_id"]), embed=applicant_embed)
    await post_application_log(interaction.guild, panel, submission, f"Application was **{status}** by {interaction.user.mention}.")


async def send_application_history(interaction: discord.Interaction, user_id: int) -> None:
    if not interaction.guild_id:
        await interaction.response.send_message("Use this inside a server.", ephemeral=True)
        return
    submissions = [
        submission
        for submission in get_guild_state(interaction.guild_id).get("submissions", {}).values()
        if int(submission.get("user_id", 0)) == user_id
    ]
    submissions.sort(key=lambda item: int(item.get("created_at", 0)), reverse=True)
    if not submissions:
        await interaction.response.send_message("No applications found for that user.", ephemeral=True)
        return

    lines = []
    for submission in submissions[:15]:
        panel = get_panel(interaction.guild_id, submission.get("panel_key", ""))
        panel_name = panel.get("name", submission.get("panel_key", "application")) if panel else submission.get("panel_key", "application")
        lines.append(
            f"`{submission['id']}` - **{panel_name}** - {submission.get('status', 'pending').title()} - "
            f"<t:{int(submission.get('created_at', utc_now()))}:R>"
        )

    embed = discord.Embed(
        title="Application history",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"Showing {min(len(submissions), 15)} of {len(submissions)} submissions")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@app_commands.command(name="createpanel", description="Create an application dropdown option")
@app_commands.describe(panel="Panel/application name", description="Short text shown in the dropdown")
async def createpanel_command(interaction: discord.Interaction, panel: str, description: Optional[str] = None):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    panel_key = normalize_panel_key(panel)
    if not panel_key:
        await interaction.response.send_message("Pick a clearer panel name.", ephemeral=True)
        return
    panels = get_guild_state(interaction.guild_id)["panels"]
    if panel_key in panels:
        await interaction.response.send_message("That panel already exists.", ephemeral=True)
        return
    panels[panel_key] = {
        "name": panel.strip()[:100],
        "description": (description or "Start this application.").strip()[:100],
        "questions": [],
        "enabled": True,
        "created_at": utc_now(),
        "created_by": interaction.user.id,
    }
    save_state()
    if interaction.guild:
        await refresh_application_message(interaction.guild)
    await interaction.response.send_message(f"Created panel `{panel_key}`.", ephemeral=True)


@app_commands.command(name="creatpanel", description="Create an application dropdown option")
@app_commands.describe(panel="Panel/application name", description="Short text shown in the dropdown")
async def creatpanel_alias_command(interaction: discord.Interaction, panel: str, description: Optional[str] = None):
    await createpanel_command.callback(interaction, panel, description)


@app_commands.command(name="editpanel", description="Edit an application dropdown option")
@app_commands.autocomplete(panel=panel_autocomplete)
async def editpanel_command(
    interaction: discord.Interaction,
    panel: str,
    new_name: Optional[str] = None,
    description: Optional[str] = None,
    open: Optional[bool] = None,
):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    panel_key = normalize_panel_key(panel)
    panel_data = get_panel(interaction.guild_id, panel_key)
    if not panel_data:
        await interaction.response.send_message("Unknown panel.", ephemeral=True)
        return
    if new_name:
        panel_data["name"] = new_name.strip()[:100]
    if description is not None:
        panel_data["description"] = description.strip()[:100]
    if open is not None:
        panel_data["enabled"] = bool(open)
    save_state()
    if interaction.guild:
        await refresh_application_message(interaction.guild)
    await interaction.response.send_message(f"Updated panel `{panel_key}`.", ephemeral=True)


@app_commands.command(name="deletepanel", description="Delete an application dropdown option")
@app_commands.autocomplete(panel=panel_autocomplete)
async def deletepanel_command(interaction: discord.Interaction, panel: str):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    panel_key = normalize_panel_key(panel)
    panels = get_guild_state(interaction.guild_id).get("panels", {})
    if panel_key not in panels:
        await interaction.response.send_message("Unknown panel.", ephemeral=True)
        return
    del panels[panel_key]
    save_state()
    if interaction.guild:
        await refresh_application_message(interaction.guild)
    await interaction.response.send_message(f"Deleted panel `{panel_key}`.", ephemeral=True)


@app_commands.command(name="addquestion", description="Add a question at a specific number")
@app_commands.autocomplete(panel=panel_autocomplete)
async def addquestion_command(interaction: discord.Interaction, panel: str, question_number: int, text: str):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    panel_data = get_panel(interaction.guild_id, normalize_panel_key(panel))
    if not panel_data:
        await interaction.response.send_message("Unknown panel.", ephemeral=True)
        return
    question = text.strip()
    if not question:
        await interaction.response.send_message("Question cannot be empty.", ephemeral=True)
        return
    questions = panel_data.setdefault("questions", [])
    insert_index = min(max(0, question_number - 1), len(questions))
    questions.insert(insert_index, question[:300])
    save_state()
    await interaction.response.send_message(f"Added question `{insert_index + 1}`. Questions were renumbered.", ephemeral=True)


@app_commands.command(name="editquestion", description="Edit a question by number")
@app_commands.autocomplete(panel=panel_autocomplete)
async def editquestion_command(interaction: discord.Interaction, panel: str, question_number: int, text: str):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    panel_data = get_panel(interaction.guild_id, normalize_panel_key(panel))
    if not panel_data:
        await interaction.response.send_message("Unknown panel.", ephemeral=True)
        return
    questions = panel_data.setdefault("questions", [])
    if question_number < 1 or question_number > len(questions):
        await interaction.response.send_message("That question number does not exist.", ephemeral=True)
        return
    questions[question_number - 1] = text.strip()[:300]
    save_state()
    await interaction.response.send_message(f"Edited question `{question_number}`.", ephemeral=True)


@app_commands.command(name="deletequestion", description="Delete a question by number")
@app_commands.autocomplete(panel=panel_autocomplete)
async def deletequestion_command(interaction: discord.Interaction, panel: str, question_number: int):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    panel_data = get_panel(interaction.guild_id, normalize_panel_key(panel))
    if not panel_data:
        await interaction.response.send_message("Unknown panel.", ephemeral=True)
        return
    questions = panel_data.setdefault("questions", [])
    if question_number < 1 or question_number > len(questions):
        await interaction.response.send_message("That question number does not exist.", ephemeral=True)
        return
    removed = questions.pop(question_number - 1)
    save_state()
    await interaction.response.send_message(
        f"Deleted question `{question_number}`: {truncate(removed, 120)}\nQuestions were renumbered.",
        ephemeral=True,
    )


@app_commands.command(name="applicationlog", description="Set the application review/log channel")
async def applicationlog_command(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    await interaction.response.defer(ephemeral=True)
    missing_permissions = bot_channel_permission_errors(channel)
    if missing_permissions:
        await interaction.followup.send(
            f"I cannot use {channel.mention} for application logs yet. Missing: {', '.join(missing_permissions)}.",
            ephemeral=True,
        )
        return
    test_embed = discord.Embed(
        title="Application log connected",
        description="New applications and review updates will be posted here.",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    try:
        await channel.send(embed=test_embed)
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"I could not send a test log message in {channel.mention}: `{truncate(error, 180)}`",
            ephemeral=True,
        )
        return
    get_guild_state(interaction.guild_id)["log_channel_id"] = channel.id
    save_state()
    await interaction.followup.send(f"Application log channel set to {channel.mention}.", ephemeral=True)


@app_commands.command(name="applicationtext", description="Set the text on the application dropdown panel")
async def applicationtext_command(interaction: discord.Interaction, text: str):
    if not await require_application_admin(interaction) or not interaction.guild_id:
        return
    get_guild_state(interaction.guild_id)["panel_text"] = text.strip()[:1000] or DEFAULT_PANEL_TEXT
    save_state()
    if interaction.guild:
        await refresh_application_message(interaction.guild)
    await interaction.response.send_message("Application panel text updated.", ephemeral=True)


@app_commands.command(name="application", description="Post or move the application dropdown panel")
async def application_command(interaction: discord.Interaction, channel: discord.TextChannel):
    if not await require_application_admin(interaction) or not interaction.guild:
        return
    guild_state = get_guild_state(interaction.guild.id)
    if not guild_state.get("panels"):
        await interaction.response.send_message("Create at least one panel first with `/createpanel`.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    missing_permissions = bot_channel_permission_errors(channel)
    if missing_permissions:
        await interaction.followup.send(
            f"I cannot post the application panel in {channel.mention}. Missing: {', '.join(missing_permissions)}.",
            ephemeral=True,
        )
        return
    try:
        message = await channel.send(
            embed=build_application_panel_embed(interaction.guild),
            view=ApplicationSelectView(interaction.guild.id),
        )
    except discord.HTTPException as error:
        await interaction.followup.send(
            f"I could not post the application panel in {channel.mention}: `{truncate(error, 180)}`",
            ephemeral=True,
        )
        return
    guild_state["application_channel_id"] = channel.id
    guild_state["application_message_id"] = message.id
    save_state()
    await interaction.followup.send(f"Application panel posted in {channel.mention}.", ephemeral=True)


@app_commands.command(name="applicationhistory", description="Find all applications for a user")
async def applicationhistory_command(interaction: discord.Interaction, user: discord.User):
    if not await require_application_admin(interaction):
        return
    await send_application_history(interaction, user.id)


async def restore_application_views() -> None:
    if BOT is None:
        return
    restored_panels = 0
    restored_reviews = 0
    for guild_id_text, guild_state in STATE.get("guilds", {}).items():
        try:
            guild_id = int(guild_id_text)
        except ValueError:
            continue
        BOT.add_view(ApplicationSelectView(guild_id))
        restored_panels += 1
        for submission_id, submission in guild_state.get("submissions", {}).items():
            if submission.get("status") != "pending" or not submission.get("review_message_id"):
                continue
            BOT.add_view(
                ApplicationReviewView(guild_id, submission_id),
                message_id=int(submission["review_message_id"]),
            )
            restored_reviews += 1
    print(f"Restored {restored_panels} application panel view(s) and {restored_reviews} review view(s).")


async def application_ready_listener() -> None:
    global VIEWS_RESTORED
    if VIEWS_RESTORED:
        return
    await restore_application_views()
    VIEWS_RESTORED = True


def setup_application_system(discord_bot: commands.Bot, data_dir: str) -> None:
    global BOT, REGISTERED, STATE, STATE_FILE, STATE_DIR
    if REGISTERED:
        return

    BOT = discord_bot
    configured_state_file = os.getenv("APPLICATION_STATE_FILE", "").strip()
    if configured_state_file:
        STATE_FILE = (
            configured_state_file
            if os.path.isabs(configured_state_file)
            else os.path.join(data_dir, configured_state_file)
        )
    else:
        STATE_FILE = os.path.join(data_dir, "applications.json")
    configured_state_dir = os.getenv("APPLICATION_STATE_DIR", "").strip()
    STATE_DIR = (
        configured_state_dir
        if configured_state_dir and os.path.isabs(configured_state_dir)
        else os.path.join(data_dir, configured_state_dir or "applications")
    )
    STATE = load_state()
    if STATE_DIR:
        os.makedirs(STATE_DIR, exist_ok=True)
        save_state()
    print(f"Application legacy import file: {os.path.abspath(STATE_FILE)}")
    print(f"Application per-server settings directory: {os.path.abspath(STATE_DIR)}")

    commands_to_add = (
        createpanel_command,
        creatpanel_alias_command,
        editpanel_command,
        deletepanel_command,
        addquestion_command,
        editquestion_command,
        deletequestion_command,
        applicationlog_command,
        applicationtext_command,
        application_command,
        applicationhistory_command,
    )
    for command in commands_to_add:
        discord_bot.tree.add_command(command)

    discord_bot.add_listener(application_ready_listener, "on_ready")
    REGISTERED = True
