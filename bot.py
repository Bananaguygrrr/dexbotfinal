from __future__ import annotations

import asyncio
import builtins
import colorsys
import json
import os
import random
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any, Dict, Iterable, Optional

import discord
from discord import app_commands
from discord.errors import HTTPException, NotFound
from discord.ext import commands, tasks
from dotenv import load_dotenv

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


def print_flush(*args, **kwargs):
    builtins.print(*args, **kwargs)
    sys.stdout.flush()


print = print_flush


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

# Add Discord user IDs here for admin-only prefix commands.
ADMIN_USER_IDS = {
    1316448831596007537,
    1105451323584938075,
}

SPAWN_THRESHOLD = max(1, int(os.getenv("SPAWN_THRESHOLD", "100")))
FRESH_SPAWN_CHANCE = min(1.0, max(0.0, float(os.getenv("FRESH_SPAWN_CHANCE", "0.005"))))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = "/var/data" if os.getenv("RENDER") and not os.getenv("DATA_DIR") else os.path.join(SCRIPT_DIR, "data")
DATA_DIR = os.getenv("DATA_DIR", DEFAULT_DATA_DIR)

USER_INVENTORIES_FILE = os.path.join(DATA_DIR, "user_inventories.json")
GUILD_CHANNEL_SETTINGS_FILE = os.path.join(DATA_DIR, "guild_channel_settings.json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
INDEX_JSON_FILE = os.path.join(DATA_DIR, "index.json")
ROOT_INDEX_JSON_FILE = os.path.join(SCRIPT_DIR, "data", "index.json")
FALLBACK_IMAGE_DIRS = (
    os.path.join(SCRIPT_DIR, "images"),
    os.path.join(SCRIPT_DIR, "data", "images"),
)
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

RARITY_ORDER = (
    "limited edition",
    "exotic",
    "legendary",
    "epic",
    "rare",
    "common",
)

RARITY_WEIGHTS = {
    "limited edition": 0.3,
    "exotic": 3,
    "legendary": 10,
    "epic": 20,
    "rare": 30,
    "common": 37,
}

RARITY_COLORS = {
    "limited edition": 0x8B0000,
    "exotic": 0xFF00FF,
    "legendary": 0xFFD700,
    "epic": 0x800080,
    "rare": 0x0000FF,
    "common": 0x808080,
}

RARITY_BUTTON_STYLE = {
    "limited edition": discord.ButtonStyle.danger,
    "exotic": discord.ButtonStyle.success,
    "legendary": discord.ButtonStyle.primary,
}


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

BOT_ONLINE = False
BOT_STARTED_AT = int(time.time())
INSTANCE_LOCK_HANDLE = None

guild_msg_counts: Dict[int, int] = {}
active_spawns: Dict[int, "CatchView"] = {}
pending_trades: Dict[tuple[int, int], int] = {}
active_trades: Dict[int, "TradeView"] = {}

INVENTORIES_CACHE: Optional[Dict[str, Dict[str, int]]] = None
GUILD_CHANNEL_SETTINGS_CACHE: Optional[Dict[str, Dict[str, int]]] = None
VEHICLES_CACHE: Dict[str, Dict[str, Any]] = {}
VEHICLES_CACHE_MTIME: Optional[float] = None
VEHICLES_CACHE_PATH: Optional[str] = None


FRESH_INVENTORY_SUFFIX = "|fresh"
NON_ALNUM_RE = re.compile(r"[^a-z0-9]")
REPEATED_CHAR_RE = re.compile(r"(.)\1+")
DIGIT_ID_RE = re.compile(r"(\d+)")

COUNT_SUFFIXES = (
    "",
    "k",
    "m",
    "b",
    "t",
    "q",
    "Q",
    "s",
    "S",
    "o",
    "n",
    "d",
    "U",
    "D",
    "T",
    "Qt",
    "Qd",
    "Sx",
    "Sp",
    "Oc",
    "No",
    "Vg",
)
COUNT_MULTIPLIER_MAP = {
    suffix: 1000 ** index
    for index, suffix in enumerate(COUNT_SUFFIXES)
    if suffix
}
COUNT_SUFFIXES_SORTED = sorted(COUNT_MULTIPLIER_MAP.keys(), key=len, reverse=True)
SHORT_COUNT_SUFFIX_MAP = {
    "k": 1_000,
    "m": 1_000_000,
    "b": 1_000_000_000,
    "t": 1_000_000_000_000,
}


def make_inventory_key(name: str, is_fresh: bool = False) -> str:
    if not name:
        return ""
    key = str(name).strip()
    if not key:
        return ""
    return f"{key}{FRESH_INVENTORY_SUFFIX}" if is_fresh else key


def split_inventory_key(key: str) -> tuple[str, bool]:
    if not key:
        return "", False
    normalized_key = str(key).strip()
    if normalized_key.endswith(FRESH_INVENTORY_SUFFIX):
        return normalized_key[: -len(FRESH_INVENTORY_SUFFIX)], True
    return normalized_key, False


def normalize_name(name: str) -> str:
    if not name:
        return ""
    cleaned = NON_ALNUM_RE.sub("", str(name).lower())
    return REPEATED_CHAR_RE.sub(r"\1", cleaned)


def display_vehicle_name(name_or_key: str) -> str:
    base_name, is_fresh = split_inventory_key(name_or_key)
    label = base_name.replace("-", "")
    return f"{label} [Fresh]" if is_fresh else label


def is_http_url(value: Any) -> bool:
    if not value:
        return False
    string_value = str(value).strip().lower()
    return string_value.startswith("http://") or string_value.startswith("https://")


def format_count(num: Any) -> str:
    if not isinstance(num, (int, float)):
        try:
            num = float(num)
        except Exception:
            return str(num)

    if abs(num) < 1000:
        return str(int(num)) if num == int(num) else str(num)

    magnitude = 0
    while abs(num) >= 1000 and magnitude < len(COUNT_SUFFIXES) - 1:
        magnitude += 1
        num /= 1000.0

    if magnitude >= len(COUNT_SUFFIXES) - 1 and abs(num) >= 1000:
        return f"{num:.2e}"

    result = f"{num:.2f}".rstrip("0").rstrip(".")
    return f"{result}{COUNT_SUFFIXES[magnitude]}"


def parse_count(text: Any) -> Optional[int]:
    if not text:
        return None

    raw = str(text).strip().replace(",", "")
    if not raw:
        return None

    for suffix in COUNT_SUFFIXES_SORTED:
        if raw.endswith(suffix):
            try:
                num_part = raw[: -len(suffix)].strip()
                if not num_part:
                    return int(COUNT_MULTIPLIER_MAP[suffix])
                return int(float(num_part) * COUNT_MULTIPLIER_MAP[suffix])
            except (TypeError, ValueError):
                continue

    try:
        last_char = raw[-1].lower()
        if last_char in SHORT_COUNT_SUFFIX_MAP:
            num_part = raw[:-1].strip()
            multiplier = SHORT_COUNT_SUFFIX_MAP[last_char]
            if not num_part:
                return int(multiplier)
            return int(float(num_part) * multiplier)
        return int(float(raw))
    except (TypeError, ValueError, IndexError):
        return None


def _coerce_non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def parse_fresh_flag(token: str) -> Optional[bool]:
    if not token:
        return None

    normalized = token.strip().lower()
    if ":" in normalized:
        key, value = normalized.split(":", 1)
    elif "=" in normalized:
        key, value = normalized.split("=", 1)
    else:
        return None

    if key != "fresh":
        return None

    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    return None


def parse_bool_true_false(token: str) -> Optional[bool]:
    normalized = (token or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def has_admin_access(message: discord.Message) -> bool:
    if message.author.id in ADMIN_USER_IDS:
        return True
    if message.guild and getattr(message.author, "guild_permissions", None):
        return bool(message.author.guild_permissions.manage_guild)
    return False


async def resolve_user_from_token(token: str, guild: Optional[discord.Guild]) -> Optional[discord.abc.User]:
    user_id_match = DIGIT_ID_RE.search(token or "")
    if not user_id_match:
        return None

    user_id = int(user_id_match.group(1))
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member

    try:
        return await bot.fetch_user(user_id)
    except Exception:
        return None


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = False) -> bool:
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
        return True
    except (NotFound, HTTPException) as error:
        command_name = interaction.command.name if interaction.command else "unknown"
        print(f"Failed to defer interaction for /{command_name}: {error}")
        return False


async def safe_send(
    interaction: discord.Interaction,
    content: Optional[str] = None,
    *,
    ephemeral: bool = False,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    wait: bool = False,
):
    try:
        kwargs: Dict[str, Any] = {"ephemeral": ephemeral}
        if content is not None:
            kwargs["content"] = content
        if embed is not None:
            kwargs["embed"] = embed
        if view is not None:
            kwargs["view"] = view

        if interaction.response.is_done():
            if wait:
                kwargs["wait"] = True
            return await interaction.followup.send(**kwargs)

        if "content" not in kwargs and "embed" not in kwargs:
            kwargs["content"] = ""
        return await interaction.response.send_message(**kwargs)
    except (NotFound, HTTPException) as error:
        command_name = interaction.command.name if interaction.command else "unknown"
        print(f"Failed to send interaction response for /{command_name}: {error}")
        return None

def _lock_file_handle(lock_file):
    if msvcrt is not None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return

    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return

    raise OSError("No supported file locking implementation is available on this platform.")


def acquire_instance_lock() -> bool:
    global INSTANCE_LOCK_HANDLE

    lock_path = os.path.join(DATA_DIR, "bot.lock")
    try:
        lock_file = open(lock_path, "a+", encoding="utf-8")
        _lock_file_handle(lock_file)
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        INSTANCE_LOCK_HANDLE = lock_file
        return True
    except OSError:
        print("Another bot instance is already running for this data directory. Stop it before starting a new one.")
        return False


def _normalize_inventory_block(items: Any) -> tuple[Dict[str, int], bool]:
    migrated = False
    normalized_items: Dict[str, int] = {}

    if isinstance(items, list):
        for item in items:
            key = make_inventory_key(item, False)
            if key:
                normalized_items[key] = normalized_items.get(key, 0) + 1
        return normalized_items, True

    if not isinstance(items, dict):
        return {}, True

    for raw_item_name, raw_item_count in items.items():
        base_name, is_fresh = split_inventory_key(str(raw_item_name))
        inventory_key = make_inventory_key(base_name, is_fresh)
        item_count = _coerce_non_negative_int(raw_item_count)

        if not inventory_key or item_count <= 0:
            migrated = True
            continue

        normalized_items[inventory_key] = normalized_items.get(inventory_key, 0) + item_count

        if inventory_key != str(raw_item_name) or item_count != raw_item_count:
            migrated = True

    if normalized_items != items:
        migrated = True

    return normalized_items, migrated


def load_inventories() -> Dict[str, Dict[str, int]]:
    global INVENTORIES_CACHE

    if INVENTORIES_CACHE is not None:
        return INVENTORIES_CACHE

    if not os.path.exists(USER_INVENTORIES_FILE):
        INVENTORIES_CACHE = {}
        save_inventories(INVENTORIES_CACHE)
        return INVENTORIES_CACHE

    try:
        with open(USER_INVENTORIES_FILE, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading {USER_INVENTORIES_FILE}: {error}")
        INVENTORIES_CACHE = {}
        return INVENTORIES_CACHE

    if not isinstance(raw_data, dict):
        INVENTORIES_CACHE = {}
        save_inventories(INVENTORIES_CACHE)
        return INVENTORIES_CACHE

    normalized_data: Dict[str, Dict[str, int]] = {}
    migrated = False

    for raw_user_id, items in raw_data.items():
        user_id_str = str(raw_user_id)
        user_inventory, block_migrated = _normalize_inventory_block(items)
        normalized_data[user_id_str] = user_inventory
        if block_migrated or user_id_str != raw_user_id:
            migrated = True

    INVENTORIES_CACHE = normalized_data
    if migrated:
        save_inventories(INVENTORIES_CACHE)

    return INVENTORIES_CACHE


def save_inventories(inventories: Dict[str, Dict[str, int]]) -> None:
    global INVENTORIES_CACHE

    try:
        os.makedirs(os.path.dirname(USER_INVENTORIES_FILE), exist_ok=True)
        with open(USER_INVENTORIES_FILE, "w", encoding="utf-8") as handle:
            json.dump(inventories, handle, indent=2, sort_keys=True)
        INVENTORIES_CACHE = inventories
    except Exception as error:
        print(f"Error saving {USER_INVENTORIES_FILE}: {error}")


def add_to_inventory(user_id: int, vehicle_name: str, is_fresh: bool = False) -> bool:
    return add_vehicle_count(user_id, vehicle_name, 1, is_fresh=is_fresh)


def add_vehicle_count(user_id: int, vehicle_name: str, count: int, is_fresh: bool = False) -> bool:
    if count <= 0:
        return False

    inventories = load_inventories()
    user_id_str = str(user_id)
    user_inventory = inventories.get(user_id_str, {})
    if not isinstance(user_inventory, dict):
        user_inventory = {}

    inventory_key = make_inventory_key(vehicle_name, is_fresh)
    if not inventory_key:
        return False

    user_inventory[inventory_key] = user_inventory.get(inventory_key, 0) + count
    inventories[user_id_str] = user_inventory
    save_inventories(inventories)
    return True


def remove_vehicle_count(user_id: int, vehicle_name: str, count: int, is_fresh: bool = False) -> int:
    if count <= 0:
        return 0

    inventories = load_inventories()
    user_id_str = str(user_id)
    user_inventory = inventories.get(user_id_str, {})
    if not isinstance(user_inventory, dict):
        return 0

    inventory_key = make_inventory_key(vehicle_name, is_fresh)
    current_count = user_inventory.get(inventory_key, 0)
    amount_removed = min(current_count, count)
    if amount_removed <= 0:
        return 0

    remaining = current_count - amount_removed
    if remaining > 0:
        user_inventory[inventory_key] = remaining
    else:
        user_inventory.pop(inventory_key, None)

    inventories[user_id_str] = user_inventory
    save_inventories(inventories)
    return amount_removed


def load_guild_channel_settings() -> Dict[str, Dict[str, int]]:
    global GUILD_CHANNEL_SETTINGS_CACHE

    if GUILD_CHANNEL_SETTINGS_CACHE is not None:
        return GUILD_CHANNEL_SETTINGS_CACHE

    if not os.path.exists(GUILD_CHANNEL_SETTINGS_FILE):
        GUILD_CHANNEL_SETTINGS_CACHE = {}
        return GUILD_CHANNEL_SETTINGS_CACHE

    try:
        with open(GUILD_CHANNEL_SETTINGS_FILE, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading {GUILD_CHANNEL_SETTINGS_FILE}: {error}")
        GUILD_CHANNEL_SETTINGS_CACHE = {}
        return GUILD_CHANNEL_SETTINGS_CACHE

    if not isinstance(raw_data, dict):
        GUILD_CHANNEL_SETTINGS_CACHE = {}
        return GUILD_CHANNEL_SETTINGS_CACHE

    normalized: Dict[str, Dict[str, int]] = {}
    for raw_guild_id, raw_settings in raw_data.items():
        guild_id = str(raw_guild_id)
        if not isinstance(raw_settings, dict):
            continue

        parsed_settings: Dict[str, int] = {}
        for key in ("dex_channel_id", "trade_channel_id"):
            value = raw_settings.get(key)
            try:
                parsed_value = int(value)
            except (TypeError, ValueError):
                continue
            if parsed_value > 0:
                parsed_settings[key] = parsed_value

        if parsed_settings:
            normalized[guild_id] = parsed_settings

    GUILD_CHANNEL_SETTINGS_CACHE = normalized
    return GUILD_CHANNEL_SETTINGS_CACHE


def save_guild_channel_settings(settings: Dict[str, Dict[str, int]]) -> None:
    global GUILD_CHANNEL_SETTINGS_CACHE

    try:
        os.makedirs(os.path.dirname(GUILD_CHANNEL_SETTINGS_FILE), exist_ok=True)
        with open(GUILD_CHANNEL_SETTINGS_FILE, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, sort_keys=True)
        GUILD_CHANNEL_SETTINGS_CACHE = settings
    except Exception as error:
        print(f"Error saving {GUILD_CHANNEL_SETTINGS_FILE}: {error}")


def get_guild_channel_setting(guild_id: int, key: str) -> Optional[int]:
    settings = load_guild_channel_settings()
    guild_settings = settings.get(str(guild_id), {})
    if not isinstance(guild_settings, dict):
        return None

    value = guild_settings.get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def set_guild_channel_setting(guild_id: int, key: str, channel_id: int) -> None:
    settings = load_guild_channel_settings()
    guild_key = str(guild_id)
    guild_settings = settings.get(guild_key, {})
    if not isinstance(guild_settings, dict):
        guild_settings = {}

    guild_settings[key] = int(channel_id)
    settings[guild_key] = guild_settings
    save_guild_channel_settings(settings)


def get_configured_text_channel(guild: discord.Guild, key: str) -> Optional[discord.TextChannel]:
    channel_id = get_guild_channel_setting(guild.id, key)
    if not channel_id:
        return None

    channel = guild.get_channel(channel_id)
    return channel if isinstance(channel, discord.TextChannel) else None


def get_configured_dex_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    return get_configured_text_channel(guild, "dex_channel_id")


def get_configured_trade_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    return get_configured_text_channel(guild, "trade_channel_id")


def _resolve_index_path() -> Optional[str]:
    if os.path.exists(INDEX_JSON_FILE):
        return INDEX_JSON_FILE
    if os.path.exists(ROOT_INDEX_JSON_FILE):
        return ROOT_INDEX_JSON_FILE
    return None


def _resolve_local_image(vehicle_name: str) -> Optional[str]:
    seen_dirs = set()
    for image_dir in (IMAGES_DIR, *FALLBACK_IMAGE_DIRS):
        if image_dir in seen_dirs:
            continue
        seen_dirs.add(image_dir)
        for extension in IMAGE_EXTENSIONS:
            test_path = os.path.join(image_dir, f"{vehicle_name}.{extension}")
            if os.path.isfile(test_path):
                return test_path
    return None


def load_vehicles() -> Dict[str, Dict[str, Any]]:
    global VEHICLES_CACHE, VEHICLES_CACHE_MTIME, VEHICLES_CACHE_PATH

    index_path = _resolve_index_path()
    if not index_path:
        return {}

    try:
        current_mtime = os.path.getmtime(index_path)
    except OSError:
        return {}

    if VEHICLES_CACHE_PATH == index_path and VEHICLES_CACHE_MTIME == current_mtime and VEHICLES_CACHE:
        return VEHICLES_CACHE

    try:
        with open(index_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as error:
        print(f"Error loading index.json ({index_path}): {error}")
        return {}

    if not isinstance(data, dict):
        VEHICLES_CACHE = {}
        VEHICLES_CACHE_PATH = index_path
        VEHICLES_CACHE_MTIME = current_mtime
        return VEHICLES_CACHE

    processed: Dict[str, Dict[str, Any]] = {}

    for raw_name, raw_value in data.items():
        vehicle_name = str(raw_name).strip()
        if not vehicle_name:
            continue

        image_url = ""
        rarity = "common"
        code = None

        if isinstance(raw_value, dict):
            image_url = str(raw_value.get("pic_link") or raw_value.get("url") or "").strip()
            rarity_value = str(raw_value.get("rarity", "Common")).strip().lower()
            rarity = rarity_value if rarity_value in RARITY_WEIGHTS else "common"
            if raw_value.get("code") is not None:
                code = str(raw_value.get("code"))
        else:
            image_url = str(raw_value).strip()

        vehicle_data: Dict[str, Any] = {
            "url": image_url,
            "rarity": rarity,
        }
        if code:
            vehicle_data["code"] = code

        local_path = _resolve_local_image(vehicle_name)
        if local_path:
            vehicle_data["local_path"] = local_path

        processed[vehicle_name] = vehicle_data

    VEHICLES_CACHE = processed
    VEHICLES_CACHE_PATH = index_path
    VEHICLES_CACHE_MTIME = current_mtime
    return VEHICLES_CACHE


def refresh_vehicles() -> Dict[str, Dict[str, Any]]:
    global VEHICLES_CACHE_PATH, VEHICLES_CACHE_MTIME
    VEHICLES_CACHE_PATH = None
    VEHICLES_CACHE_MTIME = None
    return load_vehicles()


def get_vehicle_map() -> Dict[str, Dict[str, Any]]:
    return load_vehicles()


def _vehicle_is_spawnable(vehicle_data: Dict[str, Any]) -> bool:
    return bool(vehicle_data.get("local_path") or is_http_url(vehicle_data.get("url")))


def get_random_vehicle(vehicles: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if not vehicles:
        return None

    by_rarity: Dict[str, list[str]] = {}
    for vehicle_name, vehicle_data in vehicles.items():
        if not _vehicle_is_spawnable(vehicle_data):
            continue
        rarity = str(vehicle_data.get("rarity", "common")).lower()
        by_rarity.setdefault(rarity, []).append(vehicle_name)

    if not by_rarity:
        return None

    available_rarities = [rarity for rarity in RARITY_ORDER if rarity in by_rarity]
    if not available_rarities:
        available_rarities = sorted(by_rarity.keys())

    weights = [RARITY_WEIGHTS.get(rarity, 1) for rarity in available_rarities]
    selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
    return random.choice(by_rarity[selected_rarity])


def find_best_vehicle_match(vehicle_names: Iterable[str], query: str) -> Optional[str]:
    normalized_query = normalize_name(query)
    if not normalized_query:
        return None

    scored_matches = []
    for name in vehicle_names:
        normalized_candidate = normalize_name(name)
        if not normalized_candidate:
            continue

        if normalized_candidate == normalized_query:
            return name

        if normalized_candidate.startswith(normalized_query):
            scored_matches.append((0, len(name), name.lower(), name))
        elif normalized_query in normalized_candidate:
            scored_matches.append((1, len(name), name.lower(), name))

    if not scored_matches:
        return None

    scored_matches.sort()
    return scored_matches[0][3]


def _user_rarity_counts(user_inventory: Dict[str, int], vehicles: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    counts = {rarity: 0 for rarity in RARITY_ORDER}
    for vehicle_key, count in user_inventory.items():
        if count <= 0:
            continue
        vehicle_name, _ = split_inventory_key(vehicle_key)
        vehicle_data = vehicles.get(vehicle_name)
        if not vehicle_data:
            continue
        rarity = str(vehicle_data.get("rarity", "common")).lower()
        if rarity in counts:
            counts[rarity] += count
    return counts


def create_overview_embed(user: discord.abc.User) -> discord.Embed:
    inventories = load_inventories()
    user_inventory = inventories.get(str(user.id), {})
    vehicles = get_vehicle_map()

    counts = _user_rarity_counts(user_inventory, vehicles)
    total = sum(counts.values())

    embed = discord.Embed(title=f"{user.name}'s Inventory", color=discord.Color.blue())
    if total <= 0:
        embed.description = "You have not caught any vehicles yet."
        return embed

    lines = [f"**{rarity.title()}:** {format_count(counts[rarity])}" for rarity in RARITY_ORDER]
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Total vehicles: {format_count(total)}")
    return embed


def get_user_rarity_vehicle_counts(user_id: int, rarity: str) -> Dict[str, int]:
    rarity = rarity.lower()
    inventories = load_inventories()
    user_inventory = inventories.get(str(user_id), {})
    vehicles = get_vehicle_map()

    counts: Dict[str, int] = {}
    for vehicle_key, count in user_inventory.items():
        if count <= 0:
            continue
        vehicle_name, _ = split_inventory_key(vehicle_key)
        vehicle_data = vehicles.get(vehicle_name)
        if not vehicle_data:
            continue
        if str(vehicle_data.get("rarity", "common")).lower() == rarity:
            counts[vehicle_key] = count

    return counts

class RarityButton(discord.ui.Button):
    def __init__(
        self,
        target_user: discord.abc.User,
        rarity: str,
        style: discord.ButtonStyle,
        disabled: bool,
        owner: discord.abc.User,
    ):
        super().__init__(label=rarity.title(), style=style, disabled=disabled)
        self.target_user = target_user
        self.rarity = rarity
        self.owner = owner

    async def callback(self, interaction: discord.Interaction):
        view = RarityInventoryView(self.target_user, self.rarity, self.owner)
        await interaction.response.edit_message(embed=view.create_embed(), view=view)


class InventoryOverview(discord.ui.View):
    def __init__(self, target_user: discord.abc.User, owner: discord.abc.User):
        super().__init__(timeout=120)
        self.target_user = target_user
        self.owner = owner

        inventories = load_inventories()
        user_inventory = inventories.get(str(target_user.id), {})
        vehicles = get_vehicle_map()
        counts = _user_rarity_counts(user_inventory, vehicles)

        for rarity in RARITY_ORDER:
            style = RARITY_BUTTON_STYLE.get(rarity, discord.ButtonStyle.secondary)
            count = counts.get(rarity, 0)
            self.add_item(RarityButton(target_user, rarity, style, count == 0, owner))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the person who used the command can use these buttons.",
                ephemeral=True,
            )
            return False
        return True


class RarityInventoryView(discord.ui.View):
    def __init__(self, target_user: discord.abc.User, rarity: str, owner: discord.abc.User):
        super().__init__(timeout=120)
        self.target_user = target_user
        self.rarity = rarity
        self.owner = owner
        self.vehicle_counts = get_user_rarity_vehicle_counts(target_user.id, rarity)

        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        view = InventoryOverview(self.target_user, self.owner)
        await interaction.response.edit_message(embed=create_overview_embed(self.target_user), view=view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the person who used the command can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    def create_embed(self) -> discord.Embed:
        color_value = RARITY_COLORS.get(self.rarity, 0x0000FF)
        embed = discord.Embed(
            title=f"{self.target_user.name}'s {self.rarity.title()} Vehicles",
            color=discord.Color(color_value),
        )

        if not self.vehicle_counts:
            embed.description = "No vehicles of this rarity yet."
            return embed

        sorted_items = sorted(
            self.vehicle_counts.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        lines = [
            f"- {format_count(count)} | {display_vehicle_name(vehicle_key)}"
            for vehicle_key, count in sorted_items[:30]
        ]

        total_unique = len(sorted_items)
        total_caught = sum(self.vehicle_counts.values())
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Unique: {total_unique} | Total caught: {format_count(total_caught)}")

        if total_unique > 30:
            embed.description += f"\n...and {total_unique - 30} more"

        return embed


def get_active_trade_for_user(user_id: int) -> Optional["TradeView"]:
    trade_view = active_trades.get(user_id)
    if not trade_view or trade_view.cancelled or trade_view.completed:
        return None
    return trade_view


def get_trade_offer_for_user(trade_view: "TradeView", user_id: int) -> Optional[Dict[str, int]]:
    if user_id == trade_view.user_a.id:
        return trade_view.offer_a
    if user_id == trade_view.user_b.id:
        return trade_view.offer_b
    return None


def get_trade_available_vehicles(user_id: int) -> Dict[str, int]:
    trade_view = get_active_trade_for_user(user_id)
    if not trade_view:
        return {}

    inventories = load_inventories()
    user_inventory = inventories.get(str(user_id), {})
    current_offer = get_trade_offer_for_user(trade_view, user_id) or {}

    available: Dict[str, int] = {}
    for vehicle_name, owned_count in user_inventory.items():
        remaining = owned_count - current_offer.get(vehicle_name, 0)
        if remaining > 0:
            available[vehicle_name] = remaining
    return available


class TradeView(discord.ui.View):
    def __init__(self, user_a: discord.User, user_b: discord.User):
        super().__init__(timeout=600)
        self.user_a = user_a
        self.user_b = user_b
        self.offer_a: Dict[str, int] = {}
        self.offer_b: Dict[str, int] = {}
        self.ready_a = False
        self.ready_b = False
        self.cancelled = False
        self.completed = False
        self.cancelled_by: Optional[str] = None
        self.message: Optional[discord.Message] = None
        self.countdown_task: Optional[asyncio.Task] = None
        self.countdown_remaining = 0

    def _format_offer_block(self, offer: Dict[str, int]) -> str:
        if not offer:
            return "*No vehicles added yet*"

        sorted_items = sorted(
            offer.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        lines = [
            f"- {format_count(count)} | {display_vehicle_name(name)}"
            for name, count in sorted_items[:20]
        ]
        if len(sorted_items) > 20:
            lines.append(f"...and {len(sorted_items) - 20} more")
        return "\n".join(lines)

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Vehicle Trade", color=discord.Color.gold())

        embed.add_field(
            name=f"{self.user_a.name}'s Offer",
            value=self._format_offer_block(self.offer_a),
            inline=True,
        )
        embed.add_field(
            name=f"{self.user_b.name}'s Offer",
            value=self._format_offer_block(self.offer_b),
            inline=True,
        )

        status_a = "READY" if self.ready_a else "Not Ready"
        status_b = "READY" if self.ready_b else "Not Ready"
        status_text = f"**{self.user_a.name}:** {status_a}\n**{self.user_b.name}:** {status_b}"

        if self.countdown_remaining > 0:
            status_text += f"\n\nCompleting in {self.countdown_remaining}s"

        embed.add_field(name="Status", value=status_text, inline=False)

        if self.cancelled:
            embed.title = "Trade Cancelled"
            if self.cancelled_by:
                embed.description = f"Reason: {self.cancelled_by}"
            embed.color = discord.Color.red()
        elif self.completed:
            embed.title = "Trade Completed"
            embed.color = discord.Color.green()

        return embed

    async def update_message(self):
        if self.cancelled or self.completed:
            if self.countdown_task and not self.countdown_task.done():
                self.countdown_task.cancel()
                self.countdown_task = None
                self.countdown_remaining = 0

            for item in self.children:
                item.disabled = True

            if active_trades.get(self.user_a.id) == self:
                del active_trades[self.user_a.id]
            if active_trades.get(self.user_b.id) == self:
                del active_trades[self.user_b.id]

        if self.message is None:
            return

        try:
            await self.message.edit(embed=self.create_embed(), view=self)
        except Exception as error:
            print(f"Error updating trade message: {error}")

    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success)
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user_a.id:
            self.ready_a = not self.ready_a
        elif interaction.user.id == self.user_b.id:
            self.ready_b = not self.ready_b
        else:
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return

        if self.ready_a and self.ready_b:
            if not self.countdown_task or self.countdown_task.done():
                self.countdown_task = asyncio.create_task(self.countdown_loop())
        else:
            if self.countdown_task and not self.countdown_task.done():
                self.countdown_task.cancel()
                self.countdown_task = None
            self.countdown_remaining = 0

        await interaction.response.defer()
        await self.update_message()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.user_a.id, self.user_b.id]:
            await interaction.response.send_message("You are not part of this trade.", ephemeral=True)
            return

        self.cancelled = True
        self.cancelled_by = f"Cancelled by {interaction.user.name}"
        await interaction.response.defer()
        await self.update_message()
        self.stop()

    async def countdown_loop(self):
        try:
            self.countdown_remaining = 5
            while self.countdown_remaining > 0:
                await self.update_message()
                await asyncio.sleep(1)
                self.countdown_remaining -= 1

            if self.ready_a and self.ready_b and not self.cancelled and not self.completed and self.message:
                await self.complete_trade(None)
        except asyncio.CancelledError:
            return
        finally:
            self.countdown_remaining = 0
            if not self.completed and not self.cancelled:
                await self.update_message()

    def reset_countdown(self):
        if self.countdown_task and not self.countdown_task.done():
            self.countdown_remaining = 5

    async def cancel_trade(self):
        if not self.cancelled and not self.completed:
            self.cancelled = True
            self.cancelled_by = "New trade started"
            await self.update_message()
            self.stop()

    async def on_timeout(self):
        if not self.cancelled and not self.completed:
            self.cancelled = True
            self.cancelled_by = "Trade timed out"
            await self.update_message()
            self.stop()

    async def complete_trade(self, interaction: Optional[discord.Interaction]):
        inventories = load_inventories()
        inv_a = inventories.get(str(self.user_a.id), {})
        inv_b = inventories.get(str(self.user_b.id), {})

        for name, count in self.offer_a.items():
            if inv_a.get(name, 0) < count:
                channel = interaction.channel if interaction else self.message.channel
                await channel.send(f"Trade failed: {self.user_a.name} no longer has enough {display_vehicle_name(name)}.")
                self.cancelled = True
                self.cancelled_by = f"{self.user_a.name} missing items"
                await self.update_message()
                return

        for name, count in self.offer_b.items():
            if inv_b.get(name, 0) < count:
                channel = interaction.channel if interaction else self.message.channel
                await channel.send(f"Trade failed: {self.user_b.name} no longer has enough {display_vehicle_name(name)}.")
                self.cancelled = True
                self.cancelled_by = f"{self.user_b.name} missing items"
                await self.update_message()
                return

        for name, count in self.offer_a.items():
            inv_a[name] -= count
            if inv_a[name] <= 0:
                del inv_a[name]
            inv_b[name] = inv_b.get(name, 0) + count

        for name, count in self.offer_b.items():
            inv_b[name] -= count
            if inv_b[name] <= 0:
                del inv_b[name]
            inv_a[name] = inv_a.get(name, 0) + count

        inventories[str(self.user_a.id)] = inv_a
        inventories[str(self.user_b.id)] = inv_b
        save_inventories(inventories)

        self.completed = True
        await self.update_message()
        self.stop()

def register_trade_commands(discord_bot: commands.Bot):
    async def ensure_trade_channel(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return True

        configured_channel = get_configured_trade_channel(interaction.guild)
        if configured_channel is None:
            return True

        if interaction.channel and getattr(interaction.channel, "id", None) == configured_channel.id:
            return True

        await safe_send(
            interaction,
            f"Use {configured_channel.mention} for trade commands in this server.",
            ephemeral=True,
        )
        return False

    @discord_bot.tree.command(name="inventory", description="View a vehicle inventory")
    @app_commands.describe(user="The user whose inventory you want to view")
    async def inventory_slash(interaction: discord.Interaction, user: Optional[discord.User] = None):
        target_user = user or interaction.user
        view = InventoryOverview(target_user, interaction.user)
        await interaction.response.send_message(embed=create_overview_embed(target_user), view=view)

    @discord_bot.tree.command(name="tradeadd", description="Add a vehicle to your active trade offer")
    @app_commands.guild_only()
    @app_commands.describe(vehicle_name="The vehicle to add", amount="How many to add")
    async def tradeadd_slash(interaction: discord.Interaction, vehicle_name: str, amount: str):
        if not await ensure_trade_channel(interaction):
            return

        if not await safe_defer(interaction, ephemeral=True):
            return

        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            await safe_send(interaction, "You do not have an active trade right now.", ephemeral=True)
            return

        if interaction.user.id not in [trade_view.user_a.id, trade_view.user_b.id]:
            await safe_send(interaction, "You are not part of this trade.", ephemeral=True)
            return

        parsed_amount = parse_count(amount)
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
            return

        available_vehicles = get_trade_available_vehicles(interaction.user.id)
        matched_vehicle = vehicle_name if vehicle_name in available_vehicles else find_best_vehicle_match(available_vehicles.keys(), vehicle_name)
        if not matched_vehicle:
            await safe_send(interaction, f"No vehicle matching '{vehicle_name}' found in your inventory.", ephemeral=True)
            return

        available = available_vehicles[matched_vehicle]
        if parsed_amount > available:
            await safe_send(
                interaction,
                f"You do not have enough {display_vehicle_name(matched_vehicle)}. Available: {format_count(available)}",
                ephemeral=True,
            )
            return

        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id)
        current_offer[matched_vehicle] = current_offer.get(matched_vehicle, 0) + parsed_amount

        trade_view.reset_countdown()
        await trade_view.update_message()
        await safe_send(
            interaction,
            f"Added {format_count(parsed_amount)} | {display_vehicle_name(matched_vehicle)} to your offer.",
            ephemeral=True,
        )

    @tradeadd_slash.autocomplete("vehicle_name")
    async def tradeadd_vehicle_autocomplete(interaction: discord.Interaction, current: str):
        if interaction.guild:
            configured_channel = get_configured_trade_channel(interaction.guild)
            if configured_channel and interaction.channel and getattr(interaction.channel, "id", None) != configured_channel.id:
                return []

        available_vehicles = get_trade_available_vehicles(interaction.user.id)
        current_lower = current.lower()

        sorted_items = sorted(
            available_vehicles.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        return [
            app_commands.Choice(
                name=f"{display_vehicle_name(name)} ({format_count(count)} owned)",
                value=name,
            )
            for name, count in sorted_items
            if not current_lower
            or current_lower in name.lower()
            or current_lower in display_vehicle_name(name).lower()
        ][:25]

    @discord_bot.tree.command(name="traderemove", description="Remove a vehicle from your active trade offer")
    @app_commands.guild_only()
    @app_commands.describe(vehicle_name="The vehicle to remove", amount="How many to remove")
    async def traderemove_slash(interaction: discord.Interaction, vehicle_name: str, amount: str = "1"):
        if not await ensure_trade_channel(interaction):
            return

        if not await safe_defer(interaction, ephemeral=True):
            return

        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            await safe_send(interaction, "You do not have an active trade right now.", ephemeral=True)
            return

        if interaction.user.id not in [trade_view.user_a.id, trade_view.user_b.id]:
            await safe_send(interaction, "You are not part of this trade.", ephemeral=True)
            return

        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id)
        if not current_offer:
            await safe_send(interaction, "Your offer is empty.", ephemeral=True)
            return

        parsed_amount = parse_count(amount)
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
            return

        matched_vehicle = vehicle_name if vehicle_name in current_offer else find_best_vehicle_match(current_offer.keys(), vehicle_name)
        if not matched_vehicle:
            await safe_send(interaction, f"No vehicle matching '{vehicle_name}' found in your current offer.", ephemeral=True)
            return

        amount_to_remove = min(parsed_amount, current_offer[matched_vehicle])
        current_offer[matched_vehicle] -= amount_to_remove
        if current_offer[matched_vehicle] <= 0:
            del current_offer[matched_vehicle]

        trade_view.reset_countdown()
        await trade_view.update_message()
        await safe_send(
            interaction,
            f"Removed {format_count(amount_to_remove)} | {display_vehicle_name(matched_vehicle)} from your offer.",
            ephemeral=True,
        )

    @traderemove_slash.autocomplete("vehicle_name")
    async def traderemove_vehicle_autocomplete(interaction: discord.Interaction, current: str):
        if interaction.guild:
            configured_channel = get_configured_trade_channel(interaction.guild)
            if configured_channel and interaction.channel and getattr(interaction.channel, "id", None) != configured_channel.id:
                return []

        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            return []

        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id) or {}
        current_lower = current.lower()

        sorted_items = sorted(
            current_offer.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        return [
            app_commands.Choice(
                name=f"{display_vehicle_name(name)} ({format_count(count)} in offer)",
                value=name,
            )
            for name, count in sorted_items
            if not current_lower
            or current_lower in name.lower()
            or current_lower in display_vehicle_name(name).lower()
        ][:25]

    @discord_bot.tree.command(name="trade", description="Send a trade request to another user")
    @app_commands.guild_only()
    @app_commands.describe(user="The user you want to trade with")
    async def trade_slash(interaction: discord.Interaction, user: discord.User):
        if not await ensure_trade_channel(interaction):
            return

        if not await safe_defer(interaction):
            return

        if user.id == interaction.user.id:
            await safe_send(interaction, "You cannot trade with yourself.", ephemeral=True)
            return

        if user.bot:
            await safe_send(interaction, "You cannot trade with bots.", ephemeral=True)
            return

        pending_trades[(interaction.guild.id, user.id)] = interaction.user.id
        await safe_send(
            interaction,
            f"{user.mention}, {interaction.user.mention} sent you a trade request. Use `/tradeaccept {interaction.user.name}` to start.",
        )

    @discord_bot.tree.command(name="tradeaccept", description="Accept a trade request")
    @app_commands.guild_only()
    @app_commands.describe(user="The user whose trade request you want to accept")
    async def tradeaccept_slash(interaction: discord.Interaction, user: discord.User):
        if not await ensure_trade_channel(interaction):
            return

        if not await safe_defer(interaction):
            return

        guild_id = interaction.guild.id
        pending_key = (guild_id, interaction.user.id)

        if pending_key in pending_trades and pending_trades[pending_key] == user.id:
            if user.id in active_trades:
                await active_trades[user.id].cancel_trade()
            if interaction.user.id in active_trades:
                await active_trades[interaction.user.id].cancel_trade()

            del pending_trades[pending_key]

            view = TradeView(user, interaction.user)
            active_trades[user.id] = view
            active_trades[interaction.user.id] = view
            view.message = await safe_send(
                interaction,
                f"Trade started between {user.mention} and {interaction.user.mention}.",
                embed=view.create_embed(),
                view=view,
                wait=True,
            )
            return

        await safe_send(interaction, f"You do not have a pending trade request from {user.name}.", ephemeral=True)


class CatchModal(discord.ui.Modal, title="Catch the MT vehicle"):
    guess = discord.ui.TextInput(
        label="What is the name of this MT vehicle?",
        placeholder="Enter your guess here",
        required=True,
        min_length=1,
        max_length=100,
    )

    def __init__(self, correct_name: str, vehicle_code: str, view: "CatchView"):
        super().__init__()
        self.correct_name = correct_name
        self.vehicle_code = vehicle_code
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if self.view.caught:
            await interaction.response.send_message("This MT vehicle has already been caught.", ephemeral=True)
            return

        guessed_name = normalize_name(str(self.guess.value))
        if guessed_name != normalize_name(self.correct_name):
            await interaction.response.send_message(f"{interaction.user.mention} wrong name.", ephemeral=False)
            return

        self.view.caught = True
        display_code = (
            self.vehicle_code.split(",")[0].strip()
            if isinstance(self.vehicle_code, str)
            else str(self.vehicle_code)
        )

        caught_label = self.correct_name.replace("-", "")
        awarded_fresh = self.view.is_fresh
        if awarded_fresh:
            caught_label = f"{caught_label} [Fresh]"

        await interaction.response.send_message(
            f"{interaction.user.mention} caught **{caught_label}** (`{display_code}`)",
            ephemeral=False,
        )
        add_to_inventory(interaction.user.id, self.correct_name, is_fresh=awarded_fresh)

        await self.view.update_all_messages(
            f"Captured by {interaction.user.name}: {caught_label}",
            concluded=True,
        )
        self.view.stop()


class CatchView(discord.ui.View):
    def __init__(self, vehicle_name: str, vehicle_code: str, image_url: str, rarity: str, is_fresh: bool = False):
        super().__init__(timeout=SPAWN_THRESHOLD * 60)
        self.vehicle_name = vehicle_name
        self.vehicle_code = vehicle_code
        self.image_url = image_url
        self.rarity = rarity.lower()
        self.is_fresh = is_fresh
        self.caught = False
        self.messages: list[discord.Message] = []
        self.header = "A wild Fresh MT vehicle has appeared" if self.is_fresh else "A wild MT vehicle has appeared"
        self.hue = 0.0 if self.rarity == "exotic" else None

    def add_message(self, message: discord.Message):
        self.messages.append(message)

    async def update_all_messages(
        self,
        header: Optional[str] = None,
        color: Optional[discord.Color] = None,
        *,
        concluded: bool = False,
    ):
        if header:
            self.header = header

        if self.caught or concluded:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

        if color is None:
            color = discord.Color(RARITY_COLORS.get(self.rarity, 0x0000FF))

        embed = discord.Embed(title=self.header, color=color)
        embed.set_image(url=self.image_url)

        for message in self.messages:
            try:
                await message.edit(content=None, embed=embed, view=self)
            except Exception:
                continue

    async def on_timeout(self):
        if not self.caught:
            await self.update_all_messages("The wild MT vehicle escaped", concluded=True)
            self.stop()

    @discord.ui.button(label="Catch", style=discord.ButtonStyle.primary)
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.caught:
            await interaction.response.send_message("This MT vehicle has already been caught.", ephemeral=True)
            return
        await interaction.response.send_modal(CatchModal(self.vehicle_name, self.vehicle_code, self))

def _pick_spawn_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    if not guild.text_channels:
        return None

    guild_me = guild.me or guild.get_member(bot.user.id if bot.user else 0)
    configured_channel = get_configured_dex_channel(guild)
    if configured_channel:
        if guild_me is None:
            return configured_channel
        configured_perms = configured_channel.permissions_for(guild_me)
        if configured_perms.send_messages and configured_perms.embed_links:
            return configured_channel
        print(
            f"Configured dex channel {configured_channel.name} in {guild.name} is missing "
            f"Send Messages or Embed Links permission."
        )
        return None

    channels = sorted(guild.text_channels, key=lambda channel: channel.position)

    preferred = [channel for channel in channels if channel.name.lower() == "mt-dex"]
    candidates = preferred + [channel for channel in channels if channel not in preferred]

    for channel in candidates:
        if guild_me is None:
            return channel
        perms = channel.permissions_for(guild_me)
        if perms.send_messages and perms.embed_links:
            return channel

    return None


async def spawn_vehicle(
    vehicles: Dict[str, Dict[str, Any]],
    channel: discord.abc.Messageable,
    *,
    guild: Optional[discord.Guild] = None,
    ctx: Optional[commands.Context] = None,
    force_is_fresh: Optional[bool] = None,
) -> bool:
    if not vehicles:
        if ctx:
            await ctx.send("No vehicles available.")
        return False

    target_guild = guild or (ctx.guild if ctx else None)

    if target_guild and target_guild.id in active_spawns:
        old_view = active_spawns[target_guild.id]
        if not old_view.caught and not old_view.is_finished():
            await old_view.update_all_messages("The wild MT vehicle escaped", concluded=True)
            old_view.stop()

    vehicle_name = get_random_vehicle(vehicles)
    if not vehicle_name:
        return False

    vehicle_data = vehicles[vehicle_name]
    local_path = vehicle_data.get("local_path")
    image_url = vehicle_data.get("url")
    vehicle_code = vehicle_data.get("code") or vehicle_data.get("rarity", "common")
    rarity = str(vehicle_data.get("rarity", "common"))
    if force_is_fresh is None:
        is_fresh = random.random() < FRESH_SPAWN_CHANCE
    else:
        is_fresh = bool(force_is_fresh)

    display_url = image_url if is_http_url(image_url) else None
    file = None

    if not display_url and local_path:
        try:
            file = discord.File(local_path, filename="vehicle.png")
            display_url = "attachment://vehicle.png"
        except Exception as error:
            print(f"Error opening local image for {vehicle_name}: {error}")

    if not display_url:
        print(f"Skipping vehicle without usable image: {vehicle_name}")
        return False

    print(
        f"Spawning vehicle: {vehicle_name} | rarity={rarity} | fresh={is_fresh} | "
        f"remote={bool(is_http_url(image_url))} | local={bool(local_path)}"
    )

    view = CatchView(vehicle_name, str(vehicle_code), display_url, rarity, is_fresh=is_fresh)
    if target_guild:
        active_spawns[target_guild.id] = view

    try:
        if isinstance(channel, discord.TextChannel):
            guild_me = channel.guild.me or channel.guild.get_member(bot.user.id if bot.user else 0)
            if guild_me:
                permissions = channel.permissions_for(guild_me)
                if not permissions.embed_links:
                    print(f"Missing Embed Links permission in {channel.guild.name}#{channel.name}")
                    if ctx:
                        await ctx.send("Bot is missing Embed Links permission.")
                    return False

        embed = discord.Embed(
            title=view.header,
            color=discord.Color(RARITY_COLORS.get(rarity.lower(), 0x00FF00)),
        )
        embed.set_image(url=display_url)

        sender = ctx.send if ctx else channel.send
        sent = await sender(embed=embed, file=file, view=view)
        view.add_message(sent)
        return True
    except Exception as error:
        print(f"Error sending vehicle message: {error}")
        return False


async def spawn_in_guild(guild: discord.Guild):
    vehicles = refresh_vehicles()
    channel = _pick_spawn_channel(guild)

    if channel:
        await spawn_vehicle(vehicles, channel, guild=guild)
    else:
        print(f"No suitable channel found in {guild.name}")


@tasks.loop(seconds=1)
async def rainbow_task():
    update_tasks = []

    for guild_id in list(active_spawns.keys()):
        view = active_spawns[guild_id]
        if view.is_finished() or view.caught or view.rarity != "exotic" or not view.messages:
            continue

        hue = view.hue if view.hue is not None else 0.0
        rgb = colorsys.hsv_to_rgb(hue, 1, 1)
        color = discord.Color.from_rgb(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        update_tasks.append(view.update_all_messages(color=color))
        view.hue = (hue + 0.2) % 1.0

    if update_tasks:
        await asyncio.gather(*update_tasks, return_exceptions=True)


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        payload = {"running": True, "online": bool(BOT_ONLINE)}
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_health_server():
    port_value = os.getenv("PORT")
    if not port_value:
        return

    try:
        port = int(port_value)
    except ValueError:
        print(f"Invalid PORT value: {port_value}")
        return

    def _serve():
        try:
            server = HTTPServer(("0.0.0.0", port), _HealthHandler)
            print(f"Health server listening on port {port}")
            server.serve_forever()
        except Exception as error:
            print(f"Health server error: {error}")

    Thread(target=_serve, daemon=True).start()


async def set_ready_presence():
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="!help"),
        )
        print("Presence set to online.")
    except Exception as error:
        print(f"Failed to set presence: {error}")


async def sync_all_commands():
    synced = await bot.tree.sync()
    print(f"Globally synced {len(synced)} command(s)")

    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            guild_synced = await bot.tree.sync(guild=guild)
            print(f"Guild synced {len(guild_synced)} command(s) in {guild.name}")
        except Exception as guild_error:
            print(f"Error syncing guild {guild.name}: {guild_error}")

    print(f"Sync complete. Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages.")
    return synced


register_trade_commands(bot)


@bot.tree.command(name="show", description="Show a vehicle's picture and rarity")
@app_commands.describe(vehicle_name="The name of the vehicle to show")
async def show_vehicle(interaction: discord.Interaction, vehicle_name: str):
    vehicles = get_vehicle_map()
    matched_vehicle = vehicle_name if vehicle_name in vehicles else find_best_vehicle_match(vehicles.keys(), vehicle_name)

    if not matched_vehicle:
        await interaction.response.send_message(
            f"Vehicle **{vehicle_name.replace('-', '')}** not found.",
            ephemeral=True,
        )
        return

    vehicle_data = vehicles[matched_vehicle]
    rarity = str(vehicle_data.get("rarity", "common")).lower()
    local_path = vehicle_data.get("local_path")
    image_url = vehicle_data.get("url")

    embed = discord.Embed(
        title=matched_vehicle.replace("-", ""),
        color=discord.Color(RARITY_COLORS.get(rarity, 0x808080)),
    )
    embed.add_field(name="Rarity", value=rarity.title(), inline=True)

    if is_http_url(image_url):
        embed.set_image(url=str(image_url).strip())
        await interaction.response.send_message(embed=embed)
        return

    if local_path:
        try:
            file = discord.File(local_path, filename="vehicle.png")
            embed.set_image(url="attachment://vehicle.png")
            await interaction.response.send_message(embed=embed, file=file)
            return
        except Exception as error:
            print(f"Error loading local image for /show {matched_vehicle}: {error}")

    embed.description = "This vehicle has no picture yet."
    await interaction.response.send_message(embed=embed)


@show_vehicle.autocomplete("vehicle_name")
async def show_vehicle_autocomplete(interaction: discord.Interaction, current: str):
    vehicles = get_vehicle_map()
    current_lower = current.lower()
    vehicle_names = sorted(vehicles.keys())

    return [
        app_commands.Choice(name=name.replace("-", ""), value=name)
        for name in vehicle_names
        if not current_lower
        or current_lower in name.lower()
        or current_lower in name.lower().replace("-", "")
    ][:25]


@bot.tree.command(name="dexchannel", description="Set the channel used for dex spawns in this server")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(channel="Channel where vehicles should spawn")
async def dexchannel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await safe_send(interaction, "This command can only be used in a server.", ephemeral=True)
        return

    if not interaction.permissions.manage_guild:
        await safe_send(interaction, "Only server admins can use this command.", ephemeral=True)
        return

    guild_me = interaction.guild.me or interaction.guild.get_member(bot.user.id if bot.user else 0)
    if guild_me:
        perms = channel.permissions_for(guild_me)
        missing = []
        if not perms.send_messages:
            missing.append("Send Messages")
        if not perms.embed_links:
            missing.append("Embed Links")
        if missing:
            await safe_send(
                interaction,
                f"I need {', '.join(missing)} permission in {channel.mention} before it can be set as dex channel.",
                ephemeral=True,
            )
            return

    set_guild_channel_setting(interaction.guild.id, "dex_channel_id", channel.id)
    await safe_send(interaction, f"Dex channel set to {channel.mention}.", ephemeral=True)


@bot.tree.command(name="tradechannel", description="Set the channel used for trade commands in this server")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(channel="Channel where trade commands should be used")
async def tradechannel_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        await safe_send(interaction, "This command can only be used in a server.", ephemeral=True)
        return

    if not interaction.permissions.manage_guild:
        await safe_send(interaction, "Only server admins can use this command.", ephemeral=True)
        return

    guild_me = interaction.guild.me or interaction.guild.get_member(bot.user.id if bot.user else 0)
    if guild_me:
        perms = channel.permissions_for(guild_me)
        missing = []
        if not perms.send_messages:
            missing.append("Send Messages")
        if not perms.embed_links:
            missing.append("Embed Links")
        if missing:
            await safe_send(
                interaction,
                f"I need {', '.join(missing)} permission in {channel.mention} before it can be set as trade channel.",
                ephemeral=True,
            )
            return

    set_guild_channel_setting(interaction.guild.id, "trade_channel_id", channel.id)
    await safe_send(interaction, f"Trade channel set to {channel.mention}.", ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    command_name = interaction.command.name if interaction.command else "unknown"
    print(f"App command error in /{command_name}: {error}")

    original_error = getattr(error, "original", error)
    if isinstance(original_error, (discord.NotFound, discord.HTTPException)):
        print("Interaction response failed. Ensure only one bot instance is running with this token.")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    parts = message.content.split()
    command = parts[0].lower() if parts else ""

    if command == "!testspawn":
        if not message.guild:
            await message.channel.send("This command can only be used in a server.")
            return

        if not has_admin_access(message):
            await message.channel.send("You need Manage Server permission or admin access to use this command.")
            return

        forced_fresh = None
        if len(parts) > 2:
            await message.channel.send("Usage: `!testspawn` or `!testspawn true` or `!testspawn false`")
            return

        if len(parts) == 2:
            parsed_fresh = parse_bool_true_false(parts[1])
            if parsed_fresh is None:
                await message.channel.send("Usage: `!testspawn` or `!testspawn true` or `!testspawn false`")
                return
            forced_fresh = parsed_fresh

        vehicles = refresh_vehicles()
        spawned = await spawn_vehicle(vehicles, message.channel, guild=message.guild, force_is_fresh=forced_fresh)
        if spawned:
            if forced_fresh is None:
                await message.channel.send("Test spawn sent successfully.")
            else:
                await message.channel.send(
                    f"Test spawn sent successfully (fresh forced: {'true' if forced_fresh else 'false'})."
                )
        else:
            await message.channel.send("Test spawn failed. Check channel permissions and vehicle data.")
        return

    if command in {"!addinventory", "!removeinventory"}:
        if not message.guild:
            await message.channel.send("This command can only be used in a server.")
            return

        if not has_admin_access(message):
            await message.channel.send("You need Manage Server permission or admin access to use this command.")
            return

        if len(parts) < 4:
            await message.channel.send(
                "Usage: `!addinventory @user vehicle_name count fresh:true/false`\n"
                "Usage: `!removeinventory @user vehicle_name count fresh:true/false`"
            )
            return

        target_user = await resolve_user_from_token(parts[1], message.guild)
        if target_user is None:
            await message.channel.send("Could not resolve the target user. Mention a user or provide a user ID.")
            return

        arg_tail = parts[2:]
        is_fresh = False
        parsed_fresh = parse_fresh_flag(arg_tail[-1])
        if parsed_fresh is not None:
            is_fresh = parsed_fresh
            arg_tail = arg_tail[:-1]

        if len(arg_tail) < 2:
            await message.channel.send(
                "Usage: `!addinventory @user vehicle_name count fresh:true/false`\n"
                "Usage: `!removeinventory @user vehicle_name count fresh:true/false`"
            )
            return

        amount = parse_count(arg_tail[-1])
        if amount is None or amount <= 0:
            await message.channel.send("Invalid count. Use a positive number (for example: `1`, `50`, `2k`).")
            return

        vehicle_query = " ".join(arg_tail[:-1]).strip()
        if not vehicle_query:
            await message.channel.send("Vehicle name is required.")
            return

        vehicles = get_vehicle_map()
        matched_vehicle = vehicle_query if vehicle_query in vehicles else find_best_vehicle_match(vehicles.keys(), vehicle_query)
        if not matched_vehicle:
            await message.channel.send(f"Vehicle not found: `{vehicle_query}`")
            return

        display_name = display_vehicle_name(make_inventory_key(matched_vehicle, is_fresh))
        if command == "!addinventory":
            success = add_vehicle_count(target_user.id, matched_vehicle, amount, is_fresh=is_fresh)
            if not success:
                await message.channel.send("Failed to add inventory entry.")
                return

            await message.channel.send(
                f"Added **{format_count(amount)}** x **{display_name}** to {target_user.mention}'s inventory."
            )
            return

        removed_amount = remove_vehicle_count(target_user.id, matched_vehicle, amount, is_fresh=is_fresh)
        if removed_amount <= 0:
            await message.channel.send(f"No items removed. {target_user.mention} does not have `{display_name}`.")
            return

        await message.channel.send(
            f"Removed **{format_count(removed_amount)}** x **{display_name}** from {target_user.mention}'s inventory."
        )
        return

    if command in {"!help", "!h"}:
        help_embed = discord.Embed(
            title="MT Vehicle Bot Commands",
            description=(
                "```"
                "/show - Show a vehicle's picture and rarity\n"
                "/inventory - View a vehicle inventory\n"
                "/dexchannel #channel - Set this server's spawn channel (Manage Server)\n"
                "/tradechannel #channel - Set this server's trade channel (Manage Server)\n"
                "/trade - Send a trade request to another user\n"
                "/tradeaccept - Accept a trade request\n"
                "/tradeadd - Add vehicles to a trade\n"
                "/traderemove - Remove vehicles from a trade\n"
                "!testspawn - Spawn a test vehicle (admin/manage server)\n"
                "!testspawn true|false - Force testspawn fresh state\n"
                "!addinventory @user vehicle_name count fresh:true/false - Add inventory (admin/manage server)\n"
                "!removeinventory @user vehicle_name count fresh:true/false - Remove inventory (admin/manage server)\n"
                "!sync - Manually sync slash commands"
                "```"
            ),
            color=discord.Color.blurple(),
        )
        help_embed.set_footer(text=f"Vehicles spawn automatically every {SPAWN_THRESHOLD} guild messages.")
        await message.channel.send(embed=help_embed)
        return

    if command == "!sync":
        is_admin = message.author.id in ADMIN_USER_IDS
        can_manage_guild = bool(message.guild and message.author.guild_permissions.manage_guild)

        if not (is_admin or can_manage_guild):
            await message.channel.send("You do not have permission to run !sync.")
            return

        try:
            if message.guild:
                bot.tree.copy_global_to(guild=message.guild)
                synced = await bot.tree.sync(guild=message.guild)
                scope = "Guild"
            else:
                synced = await sync_all_commands()
                scope = "Global"

            synced_names = sorted(f"/{command.name}" for command in synced)
            await message.channel.send(
                f"{scope} synced {len(synced)} slash command(s) successfully.\n"
                f"{', '.join(synced_names)}\n"
                f"Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages."
            )
        except Exception as error:
            await message.channel.send(f"Error syncing slash commands: {error}")
        return

    if message.guild:
        guild_id = message.guild.id
        guild_msg_counts[guild_id] = guild_msg_counts.get(guild_id, 0) + 1

        if guild_msg_counts[guild_id] >= SPAWN_THRESHOLD:
            guild_msg_counts[guild_id] = 0
            await spawn_in_guild(message.guild)

    await bot.process_commands(message)


@bot.event
async def on_ready():
    global BOT_ONLINE
    BOT_ONLINE = True

    print(f"Using data directory: {os.path.abspath(DATA_DIR)}")
    print(f"Loaded {len(get_vehicle_map())} vehicles from index.json")
    print(f"Bot is logged in as {bot.user.name} | pid={os.getpid()} | started={BOT_STARTED_AT}")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    print(f"message_content intent enabled in code: {bot.intents.message_content}")
    print(f"Bot ready. Commands are synced. Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages.")

    await set_ready_presence()

    if not rainbow_task.is_running():
        rainbow_task.start()


async def setup_hook():
    try:
        await sync_all_commands()
    except Exception as error:
        print(f"Error syncing tree during setup: {error}")


bot.setup_hook = setup_hook


@bot.event
async def on_disconnect():
    global BOT_ONLINE
    BOT_ONLINE = False


if __name__ == "__main__":
    print(f"Using data directory: {os.path.abspath(DATA_DIR)}")
    print(f"Loaded {len(get_vehicle_map())} vehicles from index.json")

    start_health_server()

    if not TOKEN:
        print("No DISCORD_TOKEN found. Set it in environment variables or .env.")
        raise SystemExit(1)

    if not acquire_instance_lock():
        raise SystemExit(1)

    retry_delay = 15
    max_retry_delay = 3600

    while True:
        try:
            bot.run(TOKEN)
            break
        except discord.LoginFailure as error:
            print(f"Discord login failed (token issue): {error}")
            break
        except discord.HTTPException as error:
            error_text = str(error)
            if "1015" in error_text or "You are being rate limited" in error_text:
                retry_delay = max(retry_delay, 900)
                print(f"Cloudflare/Discord rate-limit block detected. Retrying in {retry_delay}s...")
            else:
                print(f"Discord HTTP error on startup: {error}. Retrying in {retry_delay}s...")
        except Exception as error:
            print(f"Unexpected bot startup error: {error}. Retrying in {retry_delay}s...")

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, max_retry_delay)
