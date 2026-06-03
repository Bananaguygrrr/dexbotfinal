from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Optional


DEFAULT_ROUNDS = max(1, int(os.getenv("GUESS_GAME_DEFAULT_ROUNDS", "5")))
MAX_ROUNDS = max(1, int(os.getenv("GUESS_GAME_MAX_ROUNDS", "20")))
MIN_SECONDS = max(5, int(os.getenv("GUESS_GAME_MIN_SECONDS", "10")))
DEFAULT_SECONDS = max(MIN_SECONDS, int(os.getenv("GUESS_GAME_DEFAULT_SECONDS", "30")))
MAX_SECONDS = max(MIN_SECONDS, int(os.getenv("GUESS_GAME_MAX_SECONDS", "120")))
NEXT_ROUND_DELAY = max(0.0, float(os.getenv("GUESS_GAME_NEXT_ROUND_DELAY_SECONDS", "5")))
SPAWN_AVAILABLE_COLOR = 0x00FF00
SPAWN_CAUGHT_COLOR = 0xFF0000
SPAWN_DESPAWN_COLOR = 0x8A8F98

_ACTIVE_GAMES: dict[int, "VehicleGuessGame"] = {}
_INSTALLED = False


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _vehicle_label(dexbot: Any, vehicle_name: str) -> str:
    try:
        return dexbot.display_vehicle_name(vehicle_name)
    except Exception:
        return vehicle_name.replace("-", "_")


def _image_source(dexbot: Any, data: dict[str, Any]) -> tuple[str, str] | tuple[None, None]:
    url = str(data.get("url") or data.get("pic_link") or "").strip()
    if url:
        try:
            if dexbot.is_http_url(url):
                return "url", url
        except Exception:
            if url.startswith(("http://", "https://")):
                return "url", url

    local_path = str(data.get("local_path") or "").strip()
    if local_path and os.path.exists(local_path):
        return "file", local_path

    return None, None


def _guess_pool(dexbot: Any) -> list[tuple[str, dict[str, Any]]]:
    vehicles = dexbot.get_vehicle_map()
    pool: list[tuple[str, dict[str, Any]]] = []
    for name, data in vehicles.items():
        if not isinstance(data, dict):
            continue
        if hasattr(dexbot, "_vehicle_is_spawnable") and not dexbot._vehicle_is_spawnable(data):
            continue
        source_type, source_value = _image_source(dexbot, data)
        if source_type and source_value:
            pool.append((name, data))
    return pool


def _norm(dexbot: Any, value: str) -> str:
    try:
        return dexbot.normalize_name(value)
    except Exception:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _is_correct_guess(dexbot: Any, vehicle_name: str, guess: str) -> bool:
    guess = str(guess or "").strip()
    if not guess:
        return False

    canonical_guess = guess
    try:
        canonical_guess = dexbot.canonical_vehicle_name(guess)
    except Exception:
        pass
    if _norm(dexbot, canonical_guess) == _norm(dexbot, vehicle_name):
        return True

    label = _vehicle_label(dexbot, vehicle_name)
    accepted = {
        vehicle_name,
        vehicle_name.replace("-", "_"),
        vehicle_name.replace("-", " "),
        label,
        label.replace("_", "-"),
        label.replace("_", " "),
    }
    normalized_guess = _norm(dexbot, guess)
    return normalized_guess in {_norm(dexbot, value) for value in accepted}


def _patch_help(dexbot: Any) -> None:
    original = getattr(dexbot, "build_help_message", None)
    if not callable(original) or getattr(original, "_guess_game_help", False):
        return

    def build_help_message_with_game(*args: Any, **kwargs: Any) -> str:
        message = original(*args, **kwargs)
        if "`/game" in message:
            return message

        show_line = "`/show vehicle_name` - Show a vehicle's picture, rarity, and existing counts\n"
        game_line = "`/game [rounds]` - Start vehicle guessing practice; no vehicles are awarded\n"
        if show_line in message:
            return message.replace(show_line, show_line + game_line, 1)

        return message + "\n" + game_line

    build_help_message_with_game._guess_game_help = True  # type: ignore[attr-defined]
    dexbot.build_help_message = build_help_message_with_game


class VehicleGuessGame:
    def __init__(self, dexbot: Any, channel: Any, host: Any, rounds: int, seconds: int) -> None:
        self.dexbot = dexbot
        self.discord = dexbot.discord
        self.channel = channel
        self.host = host
        self.rounds = rounds
        self.seconds = seconds
        self.scores: dict[int, tuple[Any, int]] = {}
        self.current_vehicle: Optional[str] = None
        self.current_event: Optional[asyncio.Event] = None
        self.current_winner: Optional[Any] = None
        self.round_started = 0.0

    async def run(self) -> None:
        try:
            await self._announce_start()
            await asyncio.sleep(3)

            for round_number in range(1, self.rounds + 1):
                pool = _guess_pool(self.dexbot)
                if not pool:
                    await self.channel.send("No vehicles with pictures are available for the guessing game.")
                    return

                vehicle_name, data = random.choice(pool)
                self.current_vehicle = vehicle_name
                self.current_winner = None
                self.current_event = asyncio.Event()
                self.round_started = time.monotonic()

                await self._send_question(round_number, vehicle_name, data)
                timed_out = False
                try:
                    await asyncio.wait_for(self.current_event.wait(), timeout=self.seconds)
                except asyncio.TimeoutError:
                    timed_out = True

                is_last_round = round_number == self.rounds
                await self._send_result(vehicle_name, timed_out, is_last_round)
                self.current_vehicle = None
                self.current_event = None
                self.current_winner = None

                if round_number != self.rounds and NEXT_ROUND_DELAY > 0:
                    await asyncio.sleep(NEXT_ROUND_DELAY)

            await self._send_final_score()
        finally:
            _ACTIVE_GAMES.pop(getattr(self.channel, "id", 0), None)

    async def handle_guess(self, message: Any) -> bool:
        if getattr(message.author, "bot", False):
            return False

        if not self.current_vehicle or not self.current_event:
            return True

        if self.current_event.is_set():
            return True

        if not _is_correct_guess(self.dexbot, self.current_vehicle, message.content):
            return True

        self.current_winner = message.author
        user_id = int(message.author.id)
        self.scores[user_id] = (message.author, self.scores.get(user_id, (message.author, 0))[1] + 1)
        self.current_event.set()
        return True

    async def _announce_start(self) -> None:
        embed = self.discord.Embed(
            title="Vehicle Guess Training",
            description=(
                "A new vehicle guessing game will start soon.\n\n"
                f"The game will last **{self.rounds}** rounds.\n"
                "Every pictured vehicle has the same chance.\n"
                "Training mode only: no vehicles are awarded."
            ),
            color=0x4C6A3D,
        )
        embed.set_footer(text=f"Started by {getattr(self.host, 'display_name', self.host)}")
        await self.channel.send(embed=embed)

    async def _send_question(self, round_number: int, vehicle_name: str, data: dict[str, Any]) -> None:
        embed = self.discord.Embed(
            title=f"Question {round_number} of {self.rounds}",
            description=(
                "What vehicle is this?\n\n"
                f"Guessing ends in **{self.seconds} seconds**.\n"
                "Type the vehicle name in chat."
            ),
            color=SPAWN_AVAILABLE_COLOR,
        )
        embed.set_footer(text="Practice game: no inventory rewards.")

        source_type, source_value = _image_source(self.dexbot, data)
        if source_type == "url":
            embed.set_image(url=source_value)
            await self.channel.send(embed=embed)
            return

        if source_type == "file":
            filename = os.path.basename(source_value) or "vehicle.png"
            embed.set_image(url=f"attachment://{filename}")
            await self.channel.send(embed=embed, file=self.discord.File(source_value, filename=filename))
            return

        await self.channel.send(embed=embed)

    async def _send_result(self, vehicle_name: str, timed_out: bool, is_last_round: bool) -> None:
        label = _vehicle_label(self.dexbot, vehicle_name)
        next_text = (
            "This was the last round. The winner will be announced any moment."
            if is_last_round
            else f"The next round starts in {NEXT_ROUND_DELAY:.0f} seconds."
        )

        if timed_out or not self.current_winner:
            embed = self.discord.Embed(
                title="Time is up",
                description=f"Nobody guessed it. The vehicle was **{label}**.\n\n{next_text}",
                color=SPAWN_DESPAWN_COLOR,
            )
            await self.channel.send(embed=embed)
            return

        elapsed = max(0.0, time.monotonic() - self.round_started)
        embed = self.discord.Embed(
            title=f"{self.current_winner.display_name} got it right",
            description=f"The vehicle was **{label}**.\n\nAnswered in **{elapsed:.1f}s**.\n{next_text}",
            color=SPAWN_CAUGHT_COLOR,
        )
        await self.channel.send(embed=embed)

    async def _send_final_score(self) -> None:
        ranked = sorted(
            self.scores.values(),
            key=lambda item: (-item[1], getattr(item[0], "display_name", "").lower()),
        )
        place_lines = []
        for place in range(1, 4):
            if place <= len(ranked):
                member, score = ranked[place - 1]
                point_word = "Point" if score == 1 else "Points"
                place_lines.append(f"**{place}. PLACE**\n{member.mention} - {score} {point_word}")
            else:
                place_lines.append(f"**{place}. PLACE**\nNo one :(")

        description = "**The game has ended!**\n\nThese are the winners from this game:\n\n" + "\n\n".join(place_lines)

        embed = self.discord.Embed(
            title="FINISHED",
            description=description,
            color=0x4C6A3D,
        )
        embed.set_footer(text="Use /game to start another vehicle guessing practice game.")
        await self.channel.send(embed=embed)


async def _handle_guess_message(message: Any) -> bool:
    channel_id = getattr(getattr(message, "channel", None), "id", None)
    if channel_id is None:
        return False

    game = _ACTIVE_GAMES.get(int(channel_id))
    if not game:
        return False

    return await game.handle_guess(message)


def _wrap_on_message(dexbot: Any) -> None:
    original = getattr(dexbot.bot, "on_message", None)
    if not callable(original) or getattr(original, "_guess_game_wrapped", False):
        return

    async def on_message_with_guess_game(message: Any) -> None:
        if await _handle_guess_message(message):
            return
        await original(message)

    on_message_with_guess_game._guess_game_wrapped = True  # type: ignore[attr-defined]
    dexbot.bot.on_message = on_message_with_guess_game


def _install_command(dexbot: Any) -> None:
    discord = dexbot.discord
    app_commands = dexbot.app_commands

    if any(command.name == "game" for command in dexbot.bot.tree.get_commands()):
        return

    @dexbot.bot.tree.command(name="game", description="Start a vehicle guessing practice game")
    @app_commands.guild_only()
    @app_commands.describe(rounds=f"How many rounds to play (1-{MAX_ROUNDS})")
    async def game_slash(
        interaction: discord.Interaction,
        rounds: int = DEFAULT_ROUNDS,
    ) -> None:
        if not interaction.channel:
            await interaction.response.send_message("This game needs a text channel.", ephemeral=True)
            return

        channel_id = int(interaction.channel.id)
        if channel_id in _ACTIVE_GAMES:
            await interaction.response.send_message("A vehicle guessing game is already running here.", ephemeral=True)
            return

        rounds = _clamp_int(rounds, 1, MAX_ROUNDS)
        if not _guess_pool(dexbot):
            await interaction.response.send_message("No vehicles with pictures are available yet.", ephemeral=True)
            return

        game = VehicleGuessGame(dexbot, interaction.channel, interaction.user, rounds, DEFAULT_SECONDS)
        _ACTIVE_GAMES[channel_id] = game
        await interaction.response.send_message(
            f"Starting vehicle guess training: **{rounds}** rounds. No vehicles are awarded."
        )
        asyncio.create_task(game.run())


def install(dexbot: Any) -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    _install_command(dexbot)
    _wrap_on_message(dexbot)
    _patch_help(dexbot)
    _INSTALLED = True
    print("Vehicle guess training game installed. Command: /game", flush=True)
