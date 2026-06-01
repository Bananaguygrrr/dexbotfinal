from __future__ import annotations

import asyncio
import base64
import builtins
import hmac
import json
import os
import random
import re
import sys
import time
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, quote, urlparse

import discord
from discord import app_commands
from discord.errors import HTTPException, NotFound
from discord.ext import commands, tasks
from dotenv import load_dotenv

import application_system
from application_system import setup_application_system

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
DISCORD_CLIENT_ID = (
    os.getenv("DISCORD_CLIENT_ID")
    or os.getenv("DISCORD_APPLICATION_ID")
    or os.getenv("CLIENT_ID")
    or ""
).strip()
INVITE_PERMISSIONS = os.getenv("INVITE_PERMISSIONS", "2147561408").strip()
WEBSITE_TITLE = "Military Tycoon Vehicle Dex Bot"
WEBSITE_BACKGROUND_URL = os.getenv("WEBSITE_BACKGROUND_URL", "").strip()
SERVER_INVITE_URL = os.getenv("SERVER_INVITE_URL", "https://discord.gg/yWJHqqBRSJ").strip()
BOT_VERSION = os.getenv("BOT_VERSION", "Beta 1.7.0").strip() or "Beta 1.7.0"
BOT_OWNER_NAME = os.getenv("BOT_OWNER_NAME", "nissan_gtr_r35_nismo").strip() or "nissan_gtr_r35_nismo"
DEFAULT_SOURCE_CODE_URL = "https://github.com/Bananaguygrrr/dexbotfinal"
SOURCE_CODE_URL = os.getenv("SOURCE_CODE_URL", DEFAULT_SOURCE_CODE_URL).strip() or DEFAULT_SOURCE_CODE_URL
TERMS_URL = os.getenv("TERMS_URL", f"{SOURCE_CODE_URL}/blob/main/TERMS.md").strip() or f"{SOURCE_CODE_URL}/blob/main/TERMS.md"
PRIVACY_URL = os.getenv("PRIVACY_URL", f"{SOURCE_CODE_URL}/blob/main/PRIVACY.md").strip() or f"{SOURCE_CODE_URL}/blob/main/PRIVACY.md"
APPLICATION_DASHBOARD_TOKEN = (
    os.getenv("APPLICATION_DASHBOARD_TOKEN")
    or os.getenv("DASHBOARD_TOKEN")
    or ""
).strip()
APPLICATION_DASHBOARD_COOKIE = "dex_app_dashboard"

PERMISSION_OWNER_USER_ID = 1105451323584938075
INITIAL_ADMIN_USER_IDS = {
    1316448831596007537,
    PERMISSION_OWNER_USER_ID,
}

SPAWN_THRESHOLD = max(1, int(os.getenv("SPAWN_RATE", os.getenv("SPAWN_THRESHOLD", "100"))))
FRESH_SPAWN_CHANCE = min(1.0, max(0.0, float(os.getenv("FRESH_SPAWN_CHANCE", "0.005"))))
EVENT_FRESH_SPAWN_CHANCE = min(1.0, max(0.0, float(os.getenv("EVENT_FRESH_SPAWN_CHANCE", "0.05"))))
SPAWN_DESPAWN_SECONDS = max(30, int(os.getenv("SPAWN_DESPAWN_SECONDS", "240")))
EVENT_SPAWN_DESPAWN_SECONDS = max(15, int(os.getenv("EVENT_SPAWN_DESPAWN_SECONDS", "60")))
EVENT_MAX_SPAWNS = max(1, int(os.getenv("EVENT_MAX_SPAWNS", "25")))
EVENT_SPAWN_DELAY_SECONDS = min(30.0, max(0.0, float(os.getenv("EVENT_SPAWN_DELAY_SECONDS", "3"))))
COMMAND_SYNC_MODE = os.getenv("COMMAND_SYNC_MODE", "global").strip().lower()
if COMMAND_SYNC_MODE not in {"global", "guild"}:
    COMMAND_SYNC_MODE = "global"
try:
    COMMAND_SYNC_GUILD_ID = int((os.getenv("COMMAND_SYNC_GUILD_ID", "0") or "0").strip()) or None
except ValueError:
    COMMAND_SYNC_GUILD_ID = None
AUTO_RESTART_BOT = os.getenv("AUTO_RESTART_BOT", "0" if os.getenv("RENDER") else "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_INSTANCE_LOCK = os.getenv("ENABLE_INSTANCE_LOCK", "0" if os.getenv("RENDER") else "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = "/var/data" if os.getenv("RENDER") and not os.getenv("DATA_DIR") else os.path.join(SCRIPT_DIR, "data")
REQUESTED_DATA_DIR = os.getenv("DATA_DIR", DEFAULT_DATA_DIR)
DATA_DIR = REQUESTED_DATA_DIR

try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception as error:
    fallback_data_dir = os.path.join(SCRIPT_DIR, "data")
    print(f"Failed to access DATA_DIR '{DATA_DIR}': {error}. Falling back to '{fallback_data_dir}'.")
    DATA_DIR = fallback_data_dir
    os.makedirs(DATA_DIR, exist_ok=True)

USER_INVENTORIES_FILE = os.path.join(DATA_DIR, "user_inventories.json")
USER_BALANCES_FILE = os.path.join(DATA_DIR, "user_balances.json")
MARKET_LISTINGS_FILE = os.path.join(DATA_DIR, "market_listings.json")
GUILD_CHANNEL_SETTINGS_FILE = os.path.join(DATA_DIR, "guild_channel_settings.json")
ADMIN_USER_IDS_FILE = os.path.join(DATA_DIR, "admin_user_ids.json")
SPAWN_RECORDS_FILE = os.path.join(DATA_DIR, "spawn_records.json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
ROOT_INDEX_JSON_FILE = os.path.join(SCRIPT_DIR, "data", "index.json")
PERSISTENT_INDEX_JSON_FILE = os.path.join(DATA_DIR, "index.json")
MAX_SPAWN_RECORDS = 1000
INVENTORY_PAGE_SIZE = 20
SHOP_PAGE_SIZE = 5
FALLBACK_IMAGE_DIRS = (
    os.path.join(SCRIPT_DIR, "images"),
    os.path.join(SCRIPT_DIR, "data", "images"),
)
IMAGE_EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp")

try:
    os.makedirs(IMAGES_DIR, exist_ok=True)
except Exception as error:
    print(f"Failed to access image cache directory '{IMAGES_DIR}': {error}. Local image cache disabled.")
    IMAGES_DIR = ""

RARITY_ORDER = (
    "art work",
    "specials",
    "limited edition",
    "exotic",
    "legendary",
    "epic",
    "rare",
    "common",
)

RARITY_WEIGHTS = {
    "art work": 0.5,
    "specials": 0.01,
    "limited edition": 0.5,
    "exotic": 4,
    "legendary": 8,
    "epic": 19,
    "rare": 25.5,
    "common": 37.99,
}

EVENT_RARITY_WEIGHTS = {
    "art work": 1.5228,
    "specials": 1,
    "limited edition": 10,
    "exotic": 20,
    "legendary": 25,
    "epic": 29,
    "rare": 15,
    "common": 0,
}

RARITY_COLORS = {
    "art work": 0x222222,
    "specials": 0x00FF9D,
    "limited edition": 0x8B0000,
    "exotic": 0xFF00D4,
    "legendary": 0xFFD700,
    "epic": 0x800080,
    "rare": 0x0000FF,
    "common": 0x808080,
}


DEFAULT_CATCH_REWARDS = {
    "art work": 150,
    "specials": 200,
    "limited edition": 150,
    "exotic": 100,
    "legendary": 100,
    "epic": 100,
    "rare": 100,
    "common": 100,
}


def _read_money_env(name: str, default: int) -> int:
    try:
        return max(0, int(float(os.getenv(name, str(default)).strip())))
    except (TypeError, ValueError, AttributeError):
        return max(0, default)


CATCH_REWARD_BY_RARITY = {
    rarity: _read_money_env(
        f"CATCH_REWARD_{rarity.upper().replace(' ', '_')}",
        DEFAULT_CATCH_REWARDS.get(rarity, 100),
    )
    for rarity in RARITY_ORDER
}
FRESH_CATCH_BONUS = _read_money_env("FRESH_CATCH_BONUS", 50)
SELL_VEHICLE_PRICE = _read_money_env("SELL_VEHICLE_PRICE", 100)
MONEY_TRADE_ALIASES = {"money", "cash", "coin", "coins", "dollar", "dollars", "$"}
COIN_EMOJI = os.getenv("COIN_EMOJI", "\U0001FA99").strip() or "\U0001FA99"

EXOTIC_RAINBOW_COLORS = (
    0xFF00D4,  # neon magenta
    0x7A00FF,  # electric purple
    0x004CFF,  # saturated blue
    0xFF1744,  # hot red
    0xFF7A00,  # vivid orange
    0xFFE600,  # bright yellow
    0x00D95A,  # neon green
)

SPECIAL_RAINBOW_COLORS = (
    0x00FF9D,  # mint plasma
    0x00E5FF,  # electric aqua
    0xB6FF00,  # acid lime
    0xFF2BD6,  # hot pink
    0xFFFFFF,  # flash white
)

RARITY_BUTTON_STYLE = {
    "art work": discord.ButtonStyle.secondary,
    "specials": discord.ButtonStyle.secondary,
    "limited edition": discord.ButtonStyle.danger,
    "exotic": discord.ButtonStyle.success,
    "legendary": discord.ButtonStyle.primary,
}

SPAWN_HEADER = "\U0001F697 A wild MT vehicle has appeared"
DESPAWN_HEADER = "\U0001F4A8 The wild MT vehicle disappeared"
EVENT_SPAWN_LABEL = "\U0001F389 Event spawn"
FRESH_CATCH_EMOJI = "\u2728"
SPECIAL_CATCH_EMOJI = "\U0001F31F"


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
setup_application_system(bot, DATA_DIR)

BOT_ONLINE = False
BOT_STARTED_AT = int(time.time())
INSTANCE_LOCK_HANDLE = None

guild_msg_counts: Dict[int, int] = {}
active_spawns: Dict[int, list["CatchView"]] = {}
pending_trades: Dict[tuple[int, int], int] = {}
active_trades: Dict[int, "TradeView"] = {}

INVENTORIES_CACHE: Optional[Dict[str, Dict[str, int]]] = None
BALANCES_CACHE: Optional[Dict[str, int]] = None
MARKET_LISTINGS_CACHE: Optional[list[Dict[str, Any]]] = None
GUILD_CHANNEL_SETTINGS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
ADMIN_USER_IDS_CACHE: Optional[set[int]] = None
VEHICLES_CACHE: Dict[str, Dict[str, Any]] = {}
VEHICLES_CACHE_MTIME: Optional[float] = None
VEHICLES_CACHE_PATH: Optional[str] = None
VEHICLE_ALIASES_CACHE: Dict[str, str] = {}
VEHICLE_ALIASES_CACHE_SIGNATURE: Optional[tuple[tuple[str, Optional[float], Optional[int]], ...]] = None


FRESH_INVENTORY_SUFFIX = "|fresh"
NON_ALNUM_RE = re.compile(r"[^a-z0-9]")
DIGIT_ID_RE = re.compile(r"(\d+)")
NAME_TOKEN_RE = re.compile(r"[a-z0-9]+")
ORDER_INSENSITIVE_SUFFIX_TOKENS = {"liberty"}
CATALOG_AUDIT_VEHICLES = ("m50", "overlord", "c17-liberty")
CATALOG_AUDIT_ENABLED = os.getenv("CATALOG_AUDIT_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

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
    key = canonical_vehicle_name(str(name).strip())
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
    return NON_ALNUM_RE.sub("", str(name).lower())


def _index_alias_signature(path: Optional[str]) -> tuple[str, Optional[float], Optional[int]]:
    if not path:
        return ("", None, None)

    absolute_path = os.path.abspath(path)
    try:
        return (absolute_path, os.path.getmtime(path), os.path.getsize(path))
    except OSError:
        return (absolute_path, None, None)


def _iter_alias_values(raw_aliases: Any) -> Iterable[str]:
    if isinstance(raw_aliases, str):
        yield raw_aliases
        return

    if isinstance(raw_aliases, (list, tuple, set)):
        for raw_alias in raw_aliases:
            yield str(raw_alias or "")


def _name_tokens_for_order_match(name: str) -> tuple[str, ...]:
    return tuple(NAME_TOKEN_RE.findall(str(name or "").lower()))


def _clean_vehicle_key_from_tokens(tokens: Iterable[str]) -> str:
    return "-".join(token for token in tokens if token)


def _order_insensitive_signature(name: str) -> tuple[str, ...]:
    return tuple(sorted(_name_tokens_for_order_match(name)))


def _choose_order_insensitive_canonical(names: Iterable[str]) -> str:
    raw_names = [str(name or "").strip() for name in names if str(name or "").strip()]
    if not raw_names:
        return ""

    scored_names = []
    for index, raw_name in enumerate(raw_names):
        tokens = _name_tokens_for_order_match(raw_name)
        cleaned_key = _clean_vehicle_key_from_tokens(tokens)
        if not cleaned_key:
            continue

        first_token = tokens[0] if tokens else ""
        last_token = tokens[-1] if tokens else ""
        suffix_score = 0 if last_token in ORDER_INSENSITIVE_SUFFIX_TOKENS else 1
        prefix_penalty = 1 if first_token in ORDER_INSENSITIVE_SUFFIX_TOKENS else 0
        clean_score = 0 if raw_name == cleaned_key else 1
        scored_names.append((suffix_score, prefix_penalty, clean_score, index, cleaned_key))

    if not scored_names:
        return ""

    scored_names.sort()
    return scored_names[0][-1]


def _add_vehicle_alias(aliases: Dict[str, str], alias: str, target: str, *, override: bool = False) -> None:
    alias = str(alias or "").strip()
    target = str(target or "").strip()
    if not alias or not target:
        return

    for alias_variant in (
        alias,
        alias.replace("_", "-"),
        alias.replace("-", "_"),
        NON_ALNUM_RE.sub("", alias.lower()),
    ):
        alias_key = str(alias_variant or "").strip().lower()
        if not alias_key:
            continue
        existing_target = aliases.get(alias_key)
        if existing_target and existing_target != target and not override:
            continue
        aliases[alias_key] = target


def _load_vehicle_aliases_from_index(path: Optional[str]) -> Dict[str, str]:
    if not path or not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading vehicle aliases from {path}: {error}")
        return {}

    if not isinstance(raw_data, dict):
        return {}

    aliases: Dict[str, str] = {}
    order_groups: Dict[tuple[str, ...], list[str]] = {}
    normalized_groups: Dict[str, list[str]] = {}
    for raw_name, raw_value in raw_data.items():
        target = str(raw_name or "").strip()
        if not target:
            continue

        normalized_target = normalize_name(target)
        if normalized_target:
            normalized_groups.setdefault(normalized_target, []).append(target)

        signature = _order_insensitive_signature(target)
        if signature:
            order_groups.setdefault(signature, []).append(target)

        _add_vehicle_alias(aliases, target.lower(), target)
        _add_vehicle_alias(aliases, target.replace("-", "_"), target)
        _add_vehicle_alias(aliases, target.replace("_", "-"), target)

        if not isinstance(raw_value, dict):
            continue

        for raw_alias in _iter_alias_values(raw_value.get("aliases")):
            _add_vehicle_alias(aliases, raw_alias, target)

    duplicate_groups = list(normalized_groups.values()) + list(order_groups.values())
    for names in duplicate_groups:
        if len(names) <= 1:
            continue

        canonical = _choose_order_insensitive_canonical(names)
        if not canonical:
            continue

        for name in names:
            _add_vehicle_alias(aliases, name, canonical, override=True)
            _add_vehicle_alias(aliases, name.replace("-", "_"), canonical, override=True)

    return aliases


def load_vehicle_aliases() -> Dict[str, str]:
    global VEHICLE_ALIASES_CACHE, VEHICLE_ALIASES_CACHE_SIGNATURE

    index_path = _resolve_index_path()
    signature = (_index_alias_signature(index_path),)
    if VEHICLE_ALIASES_CACHE_SIGNATURE == signature:
        return VEHICLE_ALIASES_CACHE

    VEHICLE_ALIASES_CACHE = _load_vehicle_aliases_from_index(index_path)
    VEHICLE_ALIASES_CACHE_SIGNATURE = signature
    return VEHICLE_ALIASES_CACHE


def canonical_vehicle_name(name: str) -> str:
    key = str(name or "").strip()
    if not key:
        return ""

    lowered = key.lower()
    aliases = load_vehicle_aliases()
    canonical = aliases.get(lowered, aliases.get(lowered.replace("_", "-"), key))

    # Follow one extra hop so alias files can safely rename an older alias target later.
    second_hop = aliases.get(str(canonical).lower())
    return second_hop or canonical


def refresh_vehicle_aliases() -> Dict[str, str]:
    global VEHICLE_ALIASES_CACHE_SIGNATURE
    VEHICLE_ALIASES_CACHE_SIGNATURE = None
    return load_vehicle_aliases()


def display_vehicle_name(name_or_key: str) -> str:
    base_name, is_fresh = split_inventory_key(name_or_key)
    vehicle_data = VEHICLES_CACHE.get(base_name, {})
    label = str(vehicle_data.get("display_name") or base_name.replace("-", "_"))
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


def format_money(amount: Any) -> str:
    try:
        amount_int = int(amount)
    except (TypeError, ValueError):
        amount_int = 0
    return f"{amount_int:,} coins"


def format_price(amount: Any) -> str:
    return f"{COIN_EMOJI} {format_money(amount)}"


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
    if normalized == "true":
        return True
    if normalized == "false":
        return False

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


def _parse_user_id_value(value: Any) -> Optional[int]:
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        return None

    return user_id if user_id > 0 else None


def load_admin_user_ids() -> set[int]:
    global ADMIN_USER_IDS_CACHE

    if ADMIN_USER_IDS_CACHE is not None:
        return ADMIN_USER_IDS_CACHE

    if not os.path.exists(ADMIN_USER_IDS_FILE):
        ADMIN_USER_IDS_CACHE = set(INITIAL_ADMIN_USER_IDS)
        save_admin_user_ids(ADMIN_USER_IDS_CACHE)
        return ADMIN_USER_IDS_CACHE

    try:
        with open(ADMIN_USER_IDS_FILE, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading {ADMIN_USER_IDS_FILE}: {error}")
        ADMIN_USER_IDS_CACHE = set(INITIAL_ADMIN_USER_IDS)
        return ADMIN_USER_IDS_CACHE

    raw_ids = raw_data.get("admin_user_ids") if isinstance(raw_data, dict) else raw_data
    admin_ids: set[int] = set()
    if isinstance(raw_ids, list):
        for raw_user_id in raw_ids:
            parsed_user_id = _parse_user_id_value(raw_user_id)
            if parsed_user_id is not None:
                admin_ids.add(parsed_user_id)

    if not admin_ids:
        admin_ids = set(INITIAL_ADMIN_USER_IDS)

    admin_ids.add(PERMISSION_OWNER_USER_ID)
    ADMIN_USER_IDS_CACHE = admin_ids
    save_admin_user_ids(admin_ids)
    return ADMIN_USER_IDS_CACHE


def save_admin_user_ids(admin_ids: Iterable[int]) -> None:
    global ADMIN_USER_IDS_CACHE

    normalized_ids = {
        parsed_user_id
        for raw_user_id in admin_ids
        if (parsed_user_id := _parse_user_id_value(raw_user_id)) is not None
    }
    normalized_ids.add(PERMISSION_OWNER_USER_ID)

    try:
        os.makedirs(os.path.dirname(ADMIN_USER_IDS_FILE), exist_ok=True)
        with open(ADMIN_USER_IDS_FILE, "w", encoding="utf-8") as handle:
            json.dump(sorted(normalized_ids), handle, indent=2)
        ADMIN_USER_IDS_CACHE = normalized_ids
    except Exception as error:
        print(f"Error saving {ADMIN_USER_IDS_FILE}: {error}")


def has_admin_access(message: discord.Message) -> bool:
    return message.author.id in load_admin_user_ids()


def display_rarity_name(rarity: str, *, reveal_specials: bool = True) -> str:
    normalized = str(rarity or "").strip().lower()
    if normalized == "specials":
        return "Specials"
    return normalized.title()


def parse_testspawn_rarity(value: str) -> Optional[str]:
    normalized = re.sub(r"[\s_-]+", " ", str(value or "").strip().lower()).strip()
    compact = normalized.replace(" ", "")
    aliases = {
        "art": "art work",
        "artwork": "art work",
        "special": "specials",
        "specials": "specials",
        "le": "limited edition",
        "limited": "limited edition",
        "limitededition": "limited edition",
    }
    if compact in aliases:
        return aliases[compact]
    for rarity in RARITY_ORDER:
        if normalized == rarity or compact == rarity.replace(" ", ""):
            return rarity
    return None


def format_uptime(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def build_help_message() -> str:
    return (
        "**MT Vehicle Bot Commands:**\n\n"
        "**Commands Users Can Use**\n"
        "`/help` - Show this help message\n"
        "`/about` - Show bot info, stats, and links\n"
        "`/show vehicle_name` - Show a vehicle's picture, rarity, and existing counts\n"
        "`/inventory [user]` - View a vehicle inventory\n"
        "`/leaderboard` - Show vehicle and coin leaderboards\n"
        "`/shop buy` - Search and buy vehicles from other players\n"
        "`/shop sell market vehicle amount price` - List vehicles on the player market\n"
        f"`/shop sell base_price vehicle amount` - Sell vehicles instantly for {format_price(SELL_VEHICLE_PRICE)} each\n"
        "`/trade @user` - Send a trade request to another user\n"
        "`/tradeaccept @user` - Accept a trade request\n"
        "`/tradeadd item amount` - Add vehicles or coins to a trade\n"
        "`/traderemove item amount` - Remove vehicles or coins from a trade\n"
        "**Server Admins**\n"
        "`/dexchannel #channel` - Set this server's spawn channel (Manage Server)\n"
        "`/botcomment true|false` - Set wrong-name comments public or private (Manage Server)\n"
        "\n"
        "**Bot Admins**\n"
        "`!list` - Show vehicles missing pictures\n"
        "`!vehicles` - Show total caught vehicles and fresh vehicles\n"
        "`!check <message_id>` - Show the hidden vehicle name for a spawn message\n"
        "`!testspawn` - Spawn a test vehicle\n"
        "`!testspawn true|false` - Force the fresh state on a test spawn\n"
        "`!testspawn rarity [true|false]` - Spawn a test vehicle from any rarity\n"
        f"`!event <count>` - Spawn up to {EVENT_MAX_SPAWNS} event vehicles with boosted event odds\n"
        "`!addinventory @user vehicle_name count true|false` - Add inventory\n"
        "`!removeinventory @user vehicle_name count true|false` - Remove inventory\n"
        "`!addmoney @user amount` - Add coins to a user\n\n"
        "**Rarities**\n"
        "`Specials` - 0.01%\n"
        "`Limited Edition` - 0.5%\n"
        "`Exotic` - 4%\n"
        "`Legendary` - 8%\n"
        "`Epic` - 19%\n"
        "`Rare` - 30.5%\n"
        "`Common` - 37.99%\n\n"
        f"*Vehicles spawn automatically every {SPAWN_THRESHOLD} guild messages. Normal/test spawns despawn after "
        f"{SPAWN_DESPAWN_SECONDS} seconds, event spawns after {EVENT_SPAWN_DESPAWN_SECONDS} seconds.*"
    )


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


def load_balances() -> Dict[str, int]:
    global BALANCES_CACHE

    if BALANCES_CACHE is not None:
        return BALANCES_CACHE

    if not os.path.exists(USER_BALANCES_FILE):
        BALANCES_CACHE = {}
        return BALANCES_CACHE

    try:
        with open(USER_BALANCES_FILE, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading {USER_BALANCES_FILE}: {error}")
        BALANCES_CACHE = {}
        return BALANCES_CACHE

    if not isinstance(raw_data, dict):
        BALANCES_CACHE = {}
        save_balances(BALANCES_CACHE)
        return BALANCES_CACHE

    normalized: Dict[str, int] = {}
    migrated = False
    for raw_user_id, raw_balance in raw_data.items():
        user_id = str(raw_user_id)
        balance = _coerce_non_negative_int(raw_balance)
        if balance > 0:
            normalized[user_id] = balance
        if user_id != raw_user_id or balance != raw_balance:
            migrated = True

    BALANCES_CACHE = normalized
    if migrated:
        save_balances(BALANCES_CACHE)

    return BALANCES_CACHE


def save_balances(balances: Dict[str, int]) -> None:
    global BALANCES_CACHE

    normalized = {
        str(user_id): _coerce_non_negative_int(balance)
        for user_id, balance in balances.items()
        if _coerce_non_negative_int(balance) > 0
    }

    try:
        os.makedirs(os.path.dirname(USER_BALANCES_FILE), exist_ok=True)
        with open(USER_BALANCES_FILE, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
        BALANCES_CACHE = normalized
    except Exception as error:
        print(f"Error saving {USER_BALANCES_FILE}: {error}")


def get_user_balance(user_id: int) -> int:
    return _coerce_non_negative_int(load_balances().get(str(user_id), 0))


def add_money(user_id: int, amount: int) -> int:
    amount = _coerce_non_negative_int(amount)
    if amount <= 0:
        return get_user_balance(user_id)

    balances = load_balances()
    user_id_str = str(user_id)
    balances[user_id_str] = _coerce_non_negative_int(balances.get(user_id_str, 0)) + amount
    save_balances(balances)
    return balances[user_id_str]


def remove_money(user_id: int, amount: int) -> bool:
    amount = _coerce_non_negative_int(amount)
    if amount <= 0:
        return False

    balances = load_balances()
    user_id_str = str(user_id)
    current_balance = _coerce_non_negative_int(balances.get(user_id_str, 0))
    if current_balance < amount:
        return False

    remaining = current_balance - amount
    if remaining > 0:
        balances[user_id_str] = remaining
    else:
        balances.pop(user_id_str, None)
    save_balances(balances)
    return True


def get_catch_reward_for_rarity(rarity: str) -> int:
    normalized = str(rarity or "common").strip().lower()
    return _coerce_non_negative_int(CATCH_REWARD_BY_RARITY.get(normalized, CATCH_REWARD_BY_RARITY["common"]))


def get_catch_reward(rarity: str, is_fresh: bool = False) -> int:
    reward = get_catch_reward_for_rarity(rarity)
    if is_fresh:
        reward += FRESH_CATCH_BONUS
    return _coerce_non_negative_int(reward)


def is_money_trade_item(item: str) -> bool:
    normalized = str(item or "").strip().lower()
    return normalized in MONEY_TRADE_ALIASES


def make_market_listing_id(existing_ids: Optional[set[str]] = None) -> str:
    existing_ids = existing_ids or set()
    for _ in range(20):
        listing_id = f"{int(time.time() * 1000):x}{random.randint(0, 0xFFFF):04x}"[-12:]
        if listing_id not in existing_ids:
            return listing_id
    return f"{int(time.time() * 1000):x}{random.randint(0, 0xFFFFFF):06x}"


def _normalize_market_listing(raw_listing: Any, vehicles: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw_listing, dict):
        return None

    vehicle_name = canonical_vehicle_name(str(raw_listing.get("vehicle_name") or raw_listing.get("name") or ""))
    if vehicle_name not in vehicles:
        return None

    count = _coerce_non_negative_int(raw_listing.get("count", 0))
    price = _coerce_non_negative_int(raw_listing.get("price", raw_listing.get("price_each", 0)))
    seller_id = str(raw_listing.get("seller_id") or "").strip()
    if not seller_id.isdigit() or count <= 0 or price <= 0:
        return None

    listing_id = str(raw_listing.get("id") or "").strip()
    if not listing_id:
        listing_id = make_market_listing_id()

    return {
        "id": listing_id,
        "seller_id": seller_id,
        "vehicle_name": vehicle_name,
        "is_fresh": bool(raw_listing.get("is_fresh", False)),
        "count": count,
        "price": price,
        "created_at": _coerce_non_negative_int(raw_listing.get("created_at", int(time.time()))),
    }


def load_market_listings() -> list[Dict[str, Any]]:
    global MARKET_LISTINGS_CACHE

    if MARKET_LISTINGS_CACHE is not None:
        return MARKET_LISTINGS_CACHE

    if not os.path.exists(MARKET_LISTINGS_FILE):
        MARKET_LISTINGS_CACHE = []
        return MARKET_LISTINGS_CACHE

    try:
        with open(MARKET_LISTINGS_FILE, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading {MARKET_LISTINGS_FILE}: {error}")
        MARKET_LISTINGS_CACHE = []
        return MARKET_LISTINGS_CACHE

    raw_listings = raw_data.get("listings", []) if isinstance(raw_data, dict) else raw_data
    if not isinstance(raw_listings, list):
        MARKET_LISTINGS_CACHE = []
        save_market_listings(MARKET_LISTINGS_CACHE)
        return MARKET_LISTINGS_CACHE

    vehicles = get_vehicle_map()
    normalized: list[Dict[str, Any]] = []
    used_ids: set[str] = set()
    migrated = not isinstance(raw_data, list)
    for raw_listing in raw_listings:
        listing = _normalize_market_listing(raw_listing, vehicles)
        if not listing:
            migrated = True
            continue
        if listing["id"] in used_ids:
            listing["id"] = make_market_listing_id(used_ids)
            migrated = True
        used_ids.add(listing["id"])
        if listing != raw_listing:
            migrated = True
        normalized.append(listing)

    normalized.sort(key=lambda listing: int(listing.get("created_at", 0)), reverse=True)
    MARKET_LISTINGS_CACHE = normalized
    if migrated:
        save_market_listings(MARKET_LISTINGS_CACHE)
    return MARKET_LISTINGS_CACHE


def save_market_listings(listings: list[Dict[str, Any]]) -> None:
    global MARKET_LISTINGS_CACHE

    vehicles = get_vehicle_map()
    normalized: list[Dict[str, Any]] = []
    used_ids: set[str] = set()
    for raw_listing in listings:
        listing = _normalize_market_listing(raw_listing, vehicles)
        if not listing:
            continue
        if listing["id"] in used_ids:
            listing["id"] = make_market_listing_id(used_ids)
        used_ids.add(listing["id"])
        normalized.append(listing)

    normalized.sort(key=lambda listing: int(listing.get("created_at", 0)), reverse=True)
    try:
        os.makedirs(os.path.dirname(MARKET_LISTINGS_FILE), exist_ok=True)
        with open(MARKET_LISTINGS_FILE, "w", encoding="utf-8") as handle:
            json.dump(normalized, handle, indent=2, sort_keys=True)
        MARKET_LISTINGS_CACHE = normalized
    except Exception as error:
        print(f"Error saving {MARKET_LISTINGS_FILE}: {error}")


def get_listing_vehicle_key(listing: Dict[str, Any]) -> str:
    return make_inventory_key(str(listing.get("vehicle_name", "")), bool(listing.get("is_fresh", False)))


def get_listing_display_name(listing: Dict[str, Any]) -> str:
    vehicle_key = get_listing_vehicle_key(listing)
    return display_vehicle_name(vehicle_key)


def listing_matches_query(listing: Dict[str, Any], query: str) -> bool:
    if not query:
        return True
    needle = normalize_name(query)
    haystacks = {
        normalize_name(str(listing.get("vehicle_name", ""))),
        normalize_name(display_vehicle_name(str(listing.get("vehicle_name", "")))),
        normalize_name(get_listing_display_name(listing)),
    }
    return any(needle in haystack or haystack in needle for haystack in haystacks if haystack)


def get_market_listings(
    *,
    viewer_id: Optional[int] = None,
    include_own: bool = False,
    seller_id: Optional[int] = None,
    query: str = "",
) -> list[Dict[str, Any]]:
    listings = load_market_listings()
    results: list[Dict[str, Any]] = []
    for listing in listings:
        listing_seller_id = str(listing.get("seller_id", ""))
        if seller_id is not None and listing_seller_id != str(seller_id):
            continue
        if viewer_id is not None and not include_own and listing_seller_id == str(viewer_id):
            continue
        if not listing_matches_query(listing, query):
            continue
        results.append(listing)
    return results


def find_market_listing(listing_id: str) -> Optional[Dict[str, Any]]:
    listing_id = str(listing_id or "").strip()
    for listing in load_market_listings():
        if listing.get("id") == listing_id:
            return listing
    return None


def create_market_listing(seller_id: int, vehicle_key: str, count: int, price: int) -> tuple[bool, str, Optional[Dict[str, Any]]]:
    count = _coerce_non_negative_int(count)
    price = _coerce_non_negative_int(price)
    if count <= 0 or price <= 0:
        return False, "Amount and price must be positive.", None

    vehicle_name, is_fresh = split_inventory_key(vehicle_key)
    vehicle_name = canonical_vehicle_name(vehicle_name)
    if vehicle_name not in get_vehicle_map():
        return False, "That vehicle is no longer in the catalog.", None

    available_count = get_available_vehicle_counts_for_user(seller_id).get(make_inventory_key(vehicle_name, is_fresh), 0)
    if count > available_count:
        return False, f"You only have {format_count(available_count)} available {display_vehicle_name(make_inventory_key(vehicle_name, is_fresh))}."

    removed_amount = remove_vehicle_count(seller_id, vehicle_name, count, is_fresh=is_fresh)
    if removed_amount < count:
        if removed_amount > 0:
            add_vehicle_count(seller_id, vehicle_name, removed_amount, is_fresh=is_fresh)
        return False, "Listing failed. Your inventory changed before I could reserve that vehicle.", None

    listings = load_market_listings()
    listing = {
        "id": make_market_listing_id({str(item.get("id", "")) for item in listings}),
        "seller_id": str(seller_id),
        "vehicle_name": vehicle_name,
        "is_fresh": is_fresh,
        "count": count,
        "price": price,
        "created_at": int(time.time()),
    }
    listings.append(listing)
    save_market_listings(listings)
    return True, f"Listed {format_count(count)} x {get_listing_display_name(listing)} for {format_price(price)} each.", listing


def sell_vehicle_to_shop(user_id: int, vehicle_key: str, count: int) -> tuple[bool, str]:
    count = _coerce_non_negative_int(count)
    if count <= 0:
        return False, "Enter a positive amount to sell."

    vehicle_name, is_fresh = split_inventory_key(vehicle_key)
    vehicle_name = canonical_vehicle_name(vehicle_name)
    if vehicle_name not in get_vehicle_map():
        return False, "That vehicle is no longer in the catalog."

    inventory_key = make_inventory_key(vehicle_name, is_fresh)
    available_count = get_available_vehicle_counts_for_user(user_id).get(inventory_key, 0)
    if count > available_count:
        return False, f"You only have {format_count(available_count)} available {display_vehicle_name(inventory_key)}."

    removed_amount = remove_vehicle_count(user_id, vehicle_name, count, is_fresh=is_fresh)
    if removed_amount <= 0:
        return False, "Sell failed. Your inventory changed before I could remove that vehicle."

    earned = removed_amount * SELL_VEHICLE_PRICE
    add_money(user_id, earned)
    return (
        True,
        (
            f"Sold **{format_count(removed_amount)}** x **{display_vehicle_name(inventory_key)}** "
            f"for **{format_price(earned)}**. Balance: **{format_money(get_user_balance(user_id))}**"
        ),
    )


def buy_market_listing(buyer_id: int, listing_id: str, count: int) -> tuple[bool, str]:
    count = _coerce_non_negative_int(count)
    if count <= 0:
        return False, "Enter a positive amount to buy."

    listings = load_market_listings()
    listing_index = next((index for index, item in enumerate(listings) if item.get("id") == listing_id), None)
    if listing_index is None:
        return False, "That market listing no longer exists."

    listing = listings[listing_index]
    seller_id = str(listing.get("seller_id", ""))
    if seller_id == str(buyer_id):
        return False, "You cannot buy your own market listing."

    available_count = _coerce_non_negative_int(listing.get("count", 0))
    price = _coerce_non_negative_int(listing.get("price", 0))
    vehicle_name = canonical_vehicle_name(str(listing.get("vehicle_name", "")))
    is_fresh = bool(listing.get("is_fresh", False))
    if vehicle_name not in get_vehicle_map() or available_count <= 0 or price <= 0:
        listings.pop(listing_index)
        save_market_listings(listings)
        return False, "That listing was invalid and has been removed."

    if count > available_count:
        return False, f"Only {format_count(available_count)} are available in that listing."

    total_price = price * count
    if get_user_balance(buyer_id) < total_price:
        return False, f"You need {format_price(total_price)} but only have {format_money(get_user_balance(buyer_id))}."

    if not remove_money(buyer_id, total_price):
        return False, "Purchase failed. Your coin balance changed before checkout."

    add_money(int(seller_id), total_price)
    add_vehicle_count(buyer_id, vehicle_name, count, is_fresh=is_fresh)

    remaining = available_count - count
    if remaining > 0:
        listing["count"] = remaining
    else:
        listings.pop(listing_index)
    save_market_listings(listings)

    display_name = display_vehicle_name(make_inventory_key(vehicle_name, is_fresh))
    return True, f"Bought {format_count(count)} x {display_name} for {format_price(total_price)}."


def cancel_market_listing(seller_id: int, listing_id: str) -> tuple[bool, str]:
    listings = load_market_listings()
    listing_index = next((index for index, item in enumerate(listings) if item.get("id") == listing_id), None)
    if listing_index is None:
        return False, "That market listing no longer exists."

    listing = listings[listing_index]
    if str(listing.get("seller_id", "")) != str(seller_id):
        return False, "You can only cancel your own listings."

    vehicle_name = canonical_vehicle_name(str(listing.get("vehicle_name", "")))
    is_fresh = bool(listing.get("is_fresh", False))
    count = _coerce_non_negative_int(listing.get("count", 0))
    if count > 0:
        add_vehicle_count(seller_id, vehicle_name, count, is_fresh=is_fresh)
    listings.pop(listing_index)
    save_market_listings(listings)

    display_name = display_vehicle_name(make_inventory_key(vehicle_name, is_fresh))
    return True, f"Cancelled listing and returned {format_count(count)} x {display_name}."


def load_spawn_records() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(SPAWN_RECORDS_FILE):
        return {}

    try:
        with open(SPAWN_RECORDS_FILE, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception as error:
        print(f"Error loading {SPAWN_RECORDS_FILE}: {error}")
        return {}

    if not isinstance(raw_data, dict):
        return {}

    return {
        str(message_id): record
        for message_id, record in raw_data.items()
        if isinstance(record, dict)
    }


def save_spawn_records(records: Dict[str, Dict[str, Any]]) -> None:
    try:
        os.makedirs(os.path.dirname(SPAWN_RECORDS_FILE), exist_ok=True)
        with open(SPAWN_RECORDS_FILE, "w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2, sort_keys=True)
    except Exception as error:
        print(f"Error saving {SPAWN_RECORDS_FILE}: {error}")


def remember_spawn_message(message: discord.Message, view: "CatchView") -> None:
    records = load_spawn_records()
    records[str(message.id)] = {
        "vehicle_name": view.vehicle_name,
        "is_fresh": bool(view.is_fresh),
        "rarity": view.rarity,
        "guild_id": message.guild.id if message.guild else None,
        "channel_id": message.channel.id,
        "created_at": int(time.time()),
    }

    if len(records) > MAX_SPAWN_RECORDS:
        records = dict(
            sorted(
                records.items(),
                key=lambda item: int(item[1].get("created_at") or 0),
                reverse=True,
            )[:MAX_SPAWN_RECORDS]
        )

    save_spawn_records(records)


def prune_inventories_to_vehicle_names(vehicle_names: set[str]) -> None:
    if not vehicle_names:
        return

    inventories = load_inventories()
    pruned_inventories: Dict[str, Dict[str, int]] = {}
    migrated = False
    removed_entries = 0
    removed_count = 0

    for raw_user_id, user_inventory in inventories.items():
        user_id = str(raw_user_id)
        cleaned_inventory: Dict[str, int] = {}

        if not isinstance(user_inventory, dict):
            pruned_inventories[user_id] = cleaned_inventory
            migrated = True
            continue

        for raw_vehicle_key, raw_count in user_inventory.items():
            base_name, is_fresh = split_inventory_key(str(raw_vehicle_key))
            canonical_name = canonical_vehicle_name(base_name)
            inventory_key = make_inventory_key(canonical_name, is_fresh)
            item_count = _coerce_non_negative_int(raw_count)

            if not inventory_key or item_count <= 0:
                migrated = True
                continue

            if canonical_name not in vehicle_names:
                migrated = True
                removed_entries += 1
                removed_count += item_count
                continue

            cleaned_inventory[inventory_key] = cleaned_inventory.get(inventory_key, 0) + item_count
            if inventory_key != str(raw_vehicle_key) or item_count != raw_count:
                migrated = True

        if cleaned_inventory != user_inventory:
            migrated = True
        pruned_inventories[user_id] = cleaned_inventory

    if pruned_inventories != inventories:
        migrated = True

    if migrated:
        save_inventories(pruned_inventories)
        if removed_entries:
            print(
                f"Pruned {removed_entries} removed vehicle inventory entries "
                f"({removed_count} total count) after index.json update."
            )


def get_global_vehicle_counts(vehicle_name: str) -> tuple[int, int]:
    regular_count = 0
    fresh_count = 0

    for user_inventory in load_inventories().values():
        if not isinstance(user_inventory, dict):
            continue

        for vehicle_key, count in user_inventory.items():
            if count <= 0:
                continue

            base_name, is_fresh = split_inventory_key(vehicle_key)
            if base_name != vehicle_name:
                continue

            if is_fresh:
                fresh_count += count
            else:
                regular_count += count

    return regular_count, fresh_count


def get_global_inventory_totals(vehicles: Optional[Dict[str, Dict[str, Any]]] = None) -> tuple[int, int]:
    if vehicles is None:
        vehicles = get_vehicle_map()

    total_count = 0
    fresh_count = 0

    for user_inventory in load_inventories().values():
        if not isinstance(user_inventory, dict):
            continue

        for vehicle_key, raw_count in user_inventory.items():
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                continue

            if count <= 0:
                continue

            base_name, is_fresh = split_inventory_key(str(vehicle_key))
            canonical_name = canonical_vehicle_name(base_name)
            if canonical_name not in vehicles:
                continue

            total_count += count
            if is_fresh:
                fresh_count += count

    return total_count, fresh_count


def get_user_inventory_totals(user_inventory: Dict[str, int], vehicles: Dict[str, Dict[str, Any]]) -> tuple[int, int]:
    total_count = 0
    unique_vehicle_names: set[str] = set()

    if not isinstance(user_inventory, dict):
        return 0, 0

    for vehicle_key, raw_count in user_inventory.items():
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue

        if count <= 0:
            continue

        vehicle_name, _ = split_inventory_key(str(vehicle_key))
        if vehicle_name not in vehicles:
            continue

        total_count += count
        unique_vehicle_names.add(vehicle_name)

    return total_count, len(unique_vehicle_names)


def build_missing_vehicle_list_pages() -> list[str]:
    vehicles = get_vehicle_map()
    missing_vehicle_names = [
        display_vehicle_name(vehicle_name)
        for vehicle_name, vehicle_data in vehicles.items()
        if not _vehicle_has_picture(vehicle_data)
    ]
    missing_vehicle_names.sort(key=str.lower)

    if not missing_vehicle_names:
        return ["No missing vehicles."]

    pages: list[str] = []
    current_lines: list[str] = []
    current_length = 0
    max_length = 1900

    for display_name in missing_vehicle_names:
        line = f"`{display_name}`"
        line_length = len(line) + 1
        if current_lines and current_length + line_length > max_length:
            pages.append("\n".join(current_lines))
            current_lines = []
            current_length = 0

        current_lines.append(line)
        current_length += line_length

    if current_lines:
        pages.append("\n".join(current_lines))

    return pages


async def resolve_leaderboard_user_label(guild: Optional[discord.Guild], user_id: int) -> str:
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member.display_name

        try:
            member = await guild.fetch_member(user_id)
            return member.display_name
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    try:
        user = await bot.fetch_user(user_id)
        return user.name
    except (discord.NotFound, discord.HTTPException):
        return f"User {user_id}"


async def _create_vehicle_leaderboard_embed(
    guild: Optional[discord.Guild],
    viewer_id: Optional[int] = None,
) -> discord.Embed:
    inventories = load_inventories()
    vehicles = get_vehicle_map()
    leaderboard_rows: list[tuple[int, int, int]] = []

    for raw_user_id, user_inventory in inventories.items():
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue

        total_count, unique_count = get_user_inventory_totals(user_inventory, vehicles)
        if total_count <= 0:
            continue

        leaderboard_rows.append((total_count, unique_count, user_id))

    leaderboard_rows.sort(key=lambda row: (-row[0], -row[1], row[2]))

    embed = discord.Embed(title="Vehicle Leaderboard", color=discord.Color.gold())
    if not leaderboard_rows:
        embed.description = "No vehicles have been caught yet."
        if viewer_id is not None:
            embed.description += "\n\nYour rank is not ranked yet."
        return embed

    lines: list[str] = []
    for position, (total_count, unique_count, user_id) in enumerate(leaderboard_rows[:10], start=1):
        label = discord.utils.escape_markdown(await resolve_leaderboard_user_label(guild, user_id))
        lines.append(
            f"**{position}.** {label} - **{format_count(total_count)}** vehicles "
            f"({format_count(unique_count)} unique)"
        )

    if viewer_id is not None:
        viewer_rank: Optional[int] = None
        viewer_total = 0
        viewer_unique = 0
        for position, (total_count, unique_count, user_id) in enumerate(leaderboard_rows, start=1):
            if user_id == viewer_id:
                viewer_rank = position
                viewer_total = total_count
                viewer_unique = unique_count
                break

        if viewer_rank is None:
            lines.append("")
            lines.append("Your rank is not ranked yet.")
        else:
            lines.append("")
            lines.append(
                f"Your rank is **#{format_count(viewer_rank)}** with "
                f"**{format_count(viewer_total)}** vehicles ({format_count(viewer_unique)} unique)."
            )

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Ranked {format_count(len(leaderboard_rows))} players by total vehicle count")
    return embed


async def _create_money_leaderboard_embed(
    guild: Optional[discord.Guild],
    viewer_id: Optional[int] = None,
) -> discord.Embed:
    balances = load_balances()
    leaderboard_rows: list[tuple[int, int]] = []

    for raw_user_id, raw_balance in balances.items():
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue

        balance = _coerce_non_negative_int(raw_balance)
        if balance <= 0:
            continue

        leaderboard_rows.append((balance, user_id))

    leaderboard_rows.sort(key=lambda row: (-row[0], row[1]))

    embed = discord.Embed(title="Money Leaderboard", color=discord.Color.green())
    if not leaderboard_rows:
        embed.description = "No one has coins yet."
        if viewer_id is not None:
            embed.description += "\n\nYour rank is not ranked yet."
        return embed

    lines: list[str] = []
    for position, (balance, user_id) in enumerate(leaderboard_rows[:10], start=1):
        label = discord.utils.escape_markdown(await resolve_leaderboard_user_label(guild, user_id))
        lines.append(f"**{position}.** {label} - **{format_money(balance)}**")

    if viewer_id is not None:
        viewer_rank: Optional[int] = None
        viewer_balance = 0
        for position, (balance, user_id) in enumerate(leaderboard_rows, start=1):
            if user_id == viewer_id:
                viewer_rank = position
                viewer_balance = balance
                break

        lines.append("")
        if viewer_rank is None:
            lines.append("Your rank is not ranked yet.")
        else:
            lines.append(
                f"Your rank is **#{format_count(viewer_rank)}** with **{format_money(viewer_balance)}**."
            )

    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Ranked {format_count(len(leaderboard_rows))} players by coin balance")
    return embed


async def create_leaderboard_embed(
    guild: Optional[discord.Guild],
    viewer_id: Optional[int] = None,
    mode: str = "vehicles",
) -> discord.Embed:
    if str(mode or "").lower() == "money":
        return await _create_money_leaderboard_embed(guild, viewer_id)
    return await _create_vehicle_leaderboard_embed(guild, viewer_id)


class LeaderboardModeButton(discord.ui.Button):
    def __init__(self, leaderboard_view: "LeaderboardView", mode: str, label: str):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary if leaderboard_view.mode == mode else discord.ButtonStyle.secondary,
            disabled=leaderboard_view.mode == mode,
        )
        self.leaderboard_view = leaderboard_view
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        if not await safe_defer(interaction):
            return

        view = LeaderboardView(self.leaderboard_view.owner, self.mode)
        embed = await create_leaderboard_embed(interaction.guild, self.leaderboard_view.owner.id, self.mode)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except (discord.NotFound, discord.HTTPException) as error:
            print(f"Error editing leaderboard message after button click: {error}")
            if interaction.message:
                try:
                    await interaction.message.edit(embed=embed, view=view)
                except Exception as fallback_error:
                    print(f"Fallback leaderboard message edit failed: {fallback_error}")


class LeaderboardView(discord.ui.View):
    def __init__(self, owner: discord.abc.User, mode: str = "vehicles"):
        super().__init__(timeout=120)
        self.owner = owner
        self.mode = "money" if str(mode or "").lower() == "money" else "vehicles"

        self.add_item(LeaderboardModeButton(self, "vehicles", "Vehicles"))
        self.add_item(LeaderboardModeButton(self, "money", "Money"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the person who used the command can use these buttons.",
                ephemeral=True,
            )
            return False
        return True

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
    ) -> None:
        print(f"Leaderboard button error on {getattr(item, 'label', 'unknown')}: {error}")
        await safe_send(interaction, "Leaderboard button failed. Please try `/leaderboard` again.", ephemeral=True)


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


def load_guild_channel_settings() -> Dict[str, Dict[str, Any]]:
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

    normalized: Dict[str, Dict[str, Any]] = {}
    for raw_guild_id, raw_settings in raw_data.items():
        guild_id = str(raw_guild_id)
        if not isinstance(raw_settings, dict):
            continue

        parsed_settings: Dict[str, Any] = {}
        for key in ("dex_channel_id",):
            value = raw_settings.get(key)
            try:
                parsed_value = int(value)
            except (TypeError, ValueError):
                continue
            if parsed_value > 0:
                parsed_settings[key] = parsed_value

        if "bot_comment_public" in raw_settings:
            raw_public = raw_settings.get("bot_comment_public")
            if isinstance(raw_public, bool):
                parsed_settings["bot_comment_public"] = raw_public
            else:
                parsed_public = parse_bool_true_false(str(raw_public))
                if parsed_public is not None:
                    parsed_settings["bot_comment_public"] = parsed_public

        if parsed_settings:
            normalized[guild_id] = parsed_settings

    GUILD_CHANNEL_SETTINGS_CACHE = normalized
    return GUILD_CHANNEL_SETTINGS_CACHE


def save_guild_channel_settings(settings: Dict[str, Dict[str, Any]]) -> None:
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


def get_guild_bool_setting(guild_id: int, key: str, default: bool = False) -> bool:
    settings = load_guild_channel_settings()
    guild_settings = settings.get(str(guild_id), {})
    if not isinstance(guild_settings, dict):
        return default

    value = guild_settings.get(key)
    if isinstance(value, bool):
        return value

    parsed = parse_bool_true_false(str(value))
    return default if parsed is None else parsed


def set_guild_channel_setting(guild_id: int, key: str, channel_id: int) -> None:
    settings = load_guild_channel_settings()
    guild_key = str(guild_id)
    guild_settings = settings.get(guild_key, {})
    if not isinstance(guild_settings, dict):
        guild_settings = {}

    guild_settings[key] = int(channel_id)
    settings[guild_key] = guild_settings
    save_guild_channel_settings(settings)


def set_guild_bool_setting(guild_id: int, key: str, value: bool) -> None:
    settings = load_guild_channel_settings()
    guild_key = str(guild_id)
    guild_settings = settings.get(guild_key, {})
    if not isinstance(guild_settings, dict):
        guild_settings = {}

    guild_settings[key] = bool(value)
    settings[guild_key] = guild_settings
    save_guild_channel_settings(settings)


def wrong_guess_comments_are_public(guild_id: Optional[int]) -> bool:
    if guild_id is None:
        return True
    return get_guild_bool_setting(guild_id, "bot_comment_public", default=True)


def get_configured_text_channel(guild: discord.Guild, key: str) -> Optional[discord.TextChannel]:
    channel_id = get_guild_channel_setting(guild.id, key)
    if not channel_id:
        return None

    channel = guild.get_channel(channel_id)
    return channel if isinstance(channel, discord.TextChannel) else None


def get_configured_dex_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    return get_configured_text_channel(guild, "dex_channel_id")


def _get_file_mtime(path: str) -> Optional[float]:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _resolve_index_path() -> Optional[str]:
    # The vehicle catalog is deploy-time source data, not runtime state.
    # On Render, /var/data persists across deploys, so using a copied index.json
    # there can keep stale names, rarities, and image links alive forever.
    try:
        if (
            os.path.exists(PERSISTENT_INDEX_JSON_FILE)
            and os.path.abspath(PERSISTENT_INDEX_JSON_FILE) != os.path.abspath(ROOT_INDEX_JSON_FILE)
        ):
            os.remove(PERSISTENT_INDEX_JSON_FILE)
            print(f"Deleted stale persistent vehicle catalog: {PERSISTENT_INDEX_JSON_FILE}")
    except Exception as error:
        print(f"Could not delete stale persistent vehicle catalog {PERSISTENT_INDEX_JSON_FILE}: {error}")

    root_mtime = _get_file_mtime(ROOT_INDEX_JSON_FILE)
    if root_mtime is not None:
        return ROOT_INDEX_JSON_FILE

    return None


def _resolve_local_image(vehicle_name: str) -> Optional[str]:
    seen_dirs = set()
    for image_dir in (IMAGES_DIR, *FALLBACK_IMAGE_DIRS):
        if not image_dir or image_dir in seen_dirs:
            continue
        seen_dirs.add(image_dir)
        for extension in IMAGE_EXTENSIONS:
            test_path = os.path.join(image_dir, f"{vehicle_name}.{extension}")
            if os.path.isfile(test_path):
                return test_path
    return None


def _rarity_rank(rarity: Any) -> int:
    normalized = str(rarity or "").strip().lower()
    try:
        return RARITY_ORDER.index(normalized)
    except ValueError:
        return len(RARITY_ORDER)


def _rarer_rarity(existing_rarity: Any, incoming_rarity: Any) -> str:
    existing = str(existing_rarity or "common").strip().lower()
    incoming = str(incoming_rarity or "common").strip().lower()
    if _rarity_rank(incoming) < _rarity_rank(existing):
        return incoming
    return existing if existing in RARITY_WEIGHTS else "common"


def _merge_vehicle_entry(
    processed: Dict[str, Dict[str, Any]],
    vehicle_name: str,
    vehicle_data: Dict[str, Any],
    *,
    is_alias: bool,
) -> None:
    existing = processed.get(vehicle_name)
    if not existing:
        processed[vehicle_name] = vehicle_data
        return

    incoming_url = str(vehicle_data.get("url") or "").strip()
    if incoming_url and (not existing.get("url") or not is_alias):
        existing["url"] = incoming_url

    incoming_local_path = vehicle_data.get("local_path")
    if incoming_local_path and (not existing.get("local_path") or not is_alias):
        existing["local_path"] = incoming_local_path

    incoming_code = vehicle_data.get("code")
    if incoming_code and (not existing.get("code") or not is_alias):
        existing["code"] = incoming_code

    existing["rarity"] = _rarer_rarity(existing.get("rarity"), vehicle_data.get("rarity"))

    for metadata_key in ("display_name", "spawnable", "showable"):
        if metadata_key in vehicle_data and (metadata_key not in existing or not is_alias):
            existing[metadata_key] = vehicle_data[metadata_key]


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
        raw_vehicle_name = str(raw_name).strip()
        vehicle_name = canonical_vehicle_name(raw_vehicle_name)
        if not vehicle_name:
            continue
        is_alias = vehicle_name != raw_vehicle_name

        image_url = ""
        rarity = "common"
        code = None
        display_name = ""
        spawnable: Optional[bool] = None
        showable: Optional[bool] = None

        if isinstance(raw_value, dict):
            image_url = str(raw_value.get("pic_link") or raw_value.get("url") or "").strip()
            rarity_value = str(raw_value.get("rarity", "Common")).strip().lower()
            rarity = rarity_value if rarity_value in RARITY_WEIGHTS else "common"
            if raw_value.get("code") is not None:
                code = str(raw_value.get("code"))
            display_name = str(raw_value.get("display_name") or raw_value.get("name") or "").strip()
            if raw_value.get("spawnable") is not None:
                spawnable = parse_bool_true_false(str(raw_value.get("spawnable")))
            if raw_value.get("showable") is not None:
                showable = parse_bool_true_false(str(raw_value.get("showable")))
        else:
            image_url = str(raw_value).strip()

        vehicle_data: Dict[str, Any] = {
            "url": image_url,
            "rarity": rarity,
        }
        if code:
            vehicle_data["code"] = code
        if display_name:
            vehicle_data["display_name"] = display_name
        if spawnable is not None:
            vehicle_data["spawnable"] = spawnable
        if showable is not None:
            vehicle_data["showable"] = showable

        local_path = _resolve_local_image(vehicle_name)
        if not local_path and is_alias:
            local_path = _resolve_local_image(raw_vehicle_name)
        if local_path:
            vehicle_data["local_path"] = local_path

        _merge_vehicle_entry(processed, vehicle_name, vehicle_data, is_alias=is_alias)

    VEHICLES_CACHE = processed
    VEHICLES_CACHE_PATH = index_path
    VEHICLES_CACHE_MTIME = current_mtime
    prune_inventories_to_vehicle_names(set(processed.keys()))
    return VEHICLES_CACHE


def refresh_vehicles() -> Dict[str, Dict[str, Any]]:
    global VEHICLES_CACHE_PATH, VEHICLES_CACHE_MTIME
    VEHICLES_CACHE_PATH = None
    VEHICLES_CACHE_MTIME = None
    return load_vehicles()


def get_vehicle_map() -> Dict[str, Dict[str, Any]]:
    return load_vehicles()


def _raw_json_vehicle_entry(path: str, vehicle_name: str) -> Optional[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except Exception:
        return None

    if not isinstance(raw_data, dict):
        return None

    entry = raw_data.get(vehicle_name)
    return entry if isinstance(entry, dict) else None


def _format_catalog_path(path: str) -> str:
    if not path:
        return "missing"
    exists = os.path.exists(path)
    if not exists:
        return f"{path} (missing)"

    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0

    mtime = _get_file_mtime(path)
    mtime_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)) if mtime else "unknown"
    return f"{path} ({size} bytes, mtime {mtime_text})"


def _format_raw_catalog_entry(path: str, vehicle_name: str) -> str:
    entry = _raw_json_vehicle_entry(path, vehicle_name)
    if not entry:
        return "missing"

    rarity = entry.get("rarity", "missing")
    has_pic = bool(str(entry.get("pic_link") or entry.get("url") or "").strip())
    return f"rarity={rarity}, pic={'yes' if has_pic else 'no'}"


def build_catalog_debug_message(vehicle_query: str) -> str:
    aliases = refresh_vehicle_aliases()
    vehicles = refresh_vehicles()
    matched_vehicle = vehicle_query if vehicle_query in vehicles else find_best_vehicle_match(vehicles.keys(), vehicle_query)
    active_path = _resolve_index_path() or ""

    lines = [
        "**Catalog debug**",
        f"Data dir: `{os.path.abspath(DATA_DIR)}`",
        f"Active path: `{_format_catalog_path(active_path)}`",
        f"Repo path: `{_format_catalog_path(ROOT_INDEX_JSON_FILE)}`",
        f"Ignored persistent path: `{_format_catalog_path(PERSISTENT_INDEX_JSON_FILE)}`",
        f"Loaded index aliases: `{len(aliases)}`",
        f"Loaded vehicles: `{len(vehicles)}`",
    ]

    if not matched_vehicle:
        lines.append(f"Vehicle `{vehicle_query}`: not found")
        return "\n".join(lines)[:1900]

    vehicle_data = vehicles[matched_vehicle]
    rarity = str(vehicle_data.get("rarity", "missing"))
    has_pic = bool(vehicle_data.get("local_path") or is_http_url(vehicle_data.get("url")))
    lines.extend(
        [
            f"Matched: `{matched_vehicle}`",
            f"Loaded entry: rarity=`{rarity}`, pic=`{'yes' if has_pic else 'no'}`",
            f"Raw active: `{_format_raw_catalog_entry(active_path, matched_vehicle)}`",
            f"Raw repo: `{_format_raw_catalog_entry(ROOT_INDEX_JSON_FILE, matched_vehicle)}`",
            f"Raw ignored persistent: `{_format_raw_catalog_entry(PERSISTENT_INDEX_JSON_FILE, matched_vehicle)}`",
        ]
    )
    return "\n".join(lines)[:1900]


def log_catalog_audit(vehicles: Dict[str, Dict[str, Any]]) -> None:
    if not CATALOG_AUDIT_ENABLED:
        return

    for vehicle_name in CATALOG_AUDIT_VEHICLES:
        vehicle_data = vehicles.get(vehicle_name)
        if not vehicle_data:
            print(f"Catalog audit: {vehicle_name}=missing")
            continue

        rarity = str(vehicle_data.get("rarity", "missing"))
        has_pic = bool(vehicle_data.get("local_path") or is_http_url(vehicle_data.get("url")))
        print(f"Catalog audit: {vehicle_name} rarity={rarity} pic={has_pic}")


def _vehicle_has_picture(vehicle_data: Dict[str, Any]) -> bool:
    return bool(vehicle_data.get("local_path") or is_http_url(vehicle_data.get("url")))


def _vehicle_is_showable(vehicle_data: Dict[str, Any]) -> bool:
    if vehicle_data.get("showable") is False:
        return False
    return True


def _vehicle_is_spawnable(vehicle_data: Dict[str, Any]) -> bool:
    if vehicle_data.get("spawnable") is False:
        return False
    return _vehicle_has_picture(vehicle_data)


def get_random_vehicle(
    vehicles: Dict[str, Dict[str, Any]],
    rarity_weights: Optional[Dict[str, float]] = None,
) -> Optional[str]:
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

    weights_source = rarity_weights or RARITY_WEIGHTS
    default_weight = 0 if rarity_weights is not None else 1
    available_rarities = []
    available_weights = []

    ordered_rarities = list(RARITY_ORDER)
    ordered_rarities.extend(rarity for rarity in sorted(by_rarity.keys()) if rarity not in ordered_rarities)
    for rarity in ordered_rarities:
        if rarity not in by_rarity:
            continue

        weight = float(weights_source.get(rarity, default_weight))
        if weight <= 0:
            continue

        available_rarities.append(rarity)
        available_weights.append(weight)

    if not available_rarities:
        available_rarities = [rarity for rarity in ordered_rarities if rarity in by_rarity]

    if available_weights:
        selected_rarity = random.choices(available_rarities, weights=available_weights, k=1)[0]
    else:
        selected_rarity = random.choice(available_rarities)
    return random.choice(by_rarity[selected_rarity])


def prune_active_spawns(guild_id: Optional[int] = None):
    guild_ids = [guild_id] if guild_id is not None else list(active_spawns.keys())
    for current_guild_id in guild_ids:
        views = active_spawns.get(current_guild_id, [])
        remaining_views = [view for view in views if not view.is_finished()]
        if remaining_views:
            active_spawns[current_guild_id] = remaining_views
        else:
            active_spawns.pop(current_guild_id, None)


def register_active_spawn(view: "CatchView"):
    if view.guild_id is None:
        return
    prune_active_spawns(view.guild_id)
    active_spawns.setdefault(view.guild_id, []).append(view)


def unregister_active_spawn(view: "CatchView"):
    if view.guild_id is None:
        return

    views = active_spawns.get(view.guild_id, [])
    remaining_views = [existing_view for existing_view in views if existing_view is not view and not existing_view.is_finished()]
    if remaining_views:
        active_spawns[view.guild_id] = remaining_views
    else:
        active_spawns.pop(view.guild_id, None)


async def expire_active_spawns(
    guild_id: int,
    *,
    spawn_mode: Optional[str] = None,
    reason: str = DESPAWN_HEADER,
):
    existing_views = list(active_spawns.get(guild_id, []))
    kept_views: list["CatchView"] = []

    for view in existing_views:
        if view.is_finished():
            continue

        if spawn_mode is not None and view.spawn_mode != spawn_mode:
            kept_views.append(view)
            continue

        if not view.caught:
            await view.update_all_messages(reason, concluded=True)
        view.stop()

    if kept_views:
        active_spawns[guild_id] = [view for view in kept_views if not view.is_finished()]
        if not active_spawns[guild_id]:
            active_spawns.pop(guild_id, None)
    else:
        active_spawns.pop(guild_id, None)


def find_best_vehicle_match(vehicle_names: Iterable[str], query: str) -> Optional[str]:
    vehicle_names = list(vehicle_names)
    canonical_query = canonical_vehicle_name(query)
    if canonical_query in vehicle_names:
        return canonical_query

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


def get_user_inventory_count_breakdown(
    user_inventory: Dict[str, int],
    vehicles: Dict[str, Dict[str, Any]],
) -> tuple[int, int]:
    total_count = 0
    fresh_count = 0

    if not isinstance(user_inventory, dict):
        return total_count, fresh_count

    for vehicle_key, raw_count in user_inventory.items():
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue

        if count <= 0:
            continue

        vehicle_name, is_fresh = split_inventory_key(str(vehicle_key))
        vehicle_name = canonical_vehicle_name(vehicle_name)
        if vehicle_name not in vehicles:
            continue

        total_count += count
        if is_fresh:
            fresh_count += count

    return total_count, fresh_count


def create_overview_embed(user: discord.abc.User) -> discord.Embed:
    inventories = load_inventories()
    user_inventory = inventories.get(str(user.id), {})
    vehicles = get_vehicle_map()

    counts = _user_rarity_counts(user_inventory, vehicles)
    total, fresh_total = get_user_inventory_count_breakdown(user_inventory, vehicles)
    _, unique_total = get_user_inventory_totals(user_inventory, vehicles)
    money_balance = get_user_balance(user.id)

    embed = discord.Embed(title=f"{user.name}'s Inventory", color=discord.Color.blue())
    if total <= 0:
        embed.description = "You have not caught any vehicles yet."
        embed.set_footer(text=f"Coins: {format_money(money_balance)}")
        return embed

    lines = [
        f"**{display_rarity_name(rarity, reveal_specials=counts[rarity] > 0)}:** {format_count(counts[rarity])}"
        for rarity in RARITY_ORDER
    ]
    embed.description = "\n".join(lines)
    embed.set_footer(
        text=(
            f"Unique vehicles: {format_count(unique_total)} | "
            f"Total vehicles: {format_count(total)} | "
            f"Fresh vehicles: {format_count(fresh_total)} | "
            f"Coins: {format_money(money_balance)}"
        )
    )
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
        emoji = SPECIAL_CATCH_EMOJI if rarity == "specials" else None
        super().__init__(
            label=display_rarity_name(rarity, reveal_specials=not disabled),
            style=style,
            disabled=disabled,
            emoji=emoji,
        )
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
    def __init__(
        self,
        target_user: discord.abc.User,
        rarity: str,
        owner: discord.abc.User,
        page: int = 0,
    ):
        super().__init__(timeout=120)
        self.target_user = target_user
        self.rarity = rarity
        self.owner = owner
        self.vehicle_counts = get_user_rarity_vehicle_counts(target_user.id, rarity)
        sorted_items = self._sorted_items()
        self.page_count = max(1, (len(sorted_items) + INVENTORY_PAGE_SIZE - 1) // INVENTORY_PAGE_SIZE)
        self.page = min(max(0, page), self.page_count - 1)

        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_callback
        self.add_item(back_button)

        prev_button = discord.ui.Button(
            label="Prev",
            style=discord.ButtonStyle.secondary,
            disabled=self.page <= 0,
        )
        prev_button.callback = self.prev_callback
        self.add_item(prev_button)

        next_button = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.secondary,
            disabled=self.page >= self.page_count - 1,
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)

    def _sorted_items(self) -> list[tuple[str, int]]:
        return sorted(
            self.vehicle_counts.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

    async def back_callback(self, interaction: discord.Interaction):
        view = InventoryOverview(self.target_user, self.owner)
        await interaction.response.edit_message(embed=create_overview_embed(self.target_user), view=view)

    async def prev_callback(self, interaction: discord.Interaction):
        view = RarityInventoryView(self.target_user, self.rarity, self.owner, self.page - 1)
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def next_callback(self, interaction: discord.Interaction):
        view = RarityInventoryView(self.target_user, self.rarity, self.owner, self.page + 1)
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

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
            title=f"{self.target_user.name}'s {display_rarity_name(self.rarity)} Vehicles",
            color=discord.Color(color_value),
        )

        if not self.vehicle_counts:
            embed.description = "No vehicles of this rarity yet."
            return embed

        sorted_items = self._sorted_items()
        page_start = self.page * INVENTORY_PAGE_SIZE
        page_items = sorted_items[page_start : page_start + INVENTORY_PAGE_SIZE]

        lines = [
            f"- {format_count(count)} | {display_vehicle_name(vehicle_key)}"
            for vehicle_key, count in page_items
        ]

        total_unique = len(sorted_items)
        total_caught = sum(self.vehicle_counts.values())
        fresh_caught = sum(
            count
            for vehicle_key, count in self.vehicle_counts.items()
            if split_inventory_key(vehicle_key)[1]
        )
        embed.description = "\n".join(lines)
        embed.set_footer(
            text=(
                f"Unique: {total_unique} | "
                f"Total caught: {format_count(total_caught)} | "
                f"Fresh vehicles: {format_count(fresh_caught)} | "
                f"Page {self.page + 1}/{self.page_count}"
            )
        )

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


def get_available_vehicle_counts(user_id: int, current_offer: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    inventories = load_inventories()
    user_inventory = inventories.get(str(user_id), {})
    if not isinstance(user_inventory, dict):
        return {}

    current_offer = current_offer or {}
    available: Dict[str, int] = {}
    for vehicle_name, owned_count in user_inventory.items():
        remaining = _coerce_non_negative_int(owned_count) - _coerce_non_negative_int(current_offer.get(vehicle_name, 0))
        if remaining > 0:
            available[vehicle_name] = remaining
    return available


def get_trade_available_vehicles(user_id: int) -> Dict[str, int]:
    trade_view = get_active_trade_for_user(user_id)
    if not trade_view:
        return {}

    current_offer = get_trade_offer_for_user(trade_view, user_id) or {}
    return get_available_vehicle_counts(user_id, current_offer)


class TradeView(discord.ui.View):
    def __init__(self, user_a: discord.User, user_b: discord.User):
        super().__init__(timeout=600)
        self.user_a = user_a
        self.user_b = user_b
        self.offer_a: Dict[str, int] = {}
        self.offer_b: Dict[str, int] = {}
        self.money_offer_a = 0
        self.money_offer_b = 0
        self.ready_a = False
        self.ready_b = False
        self.cancelled = False
        self.completed = False
        self.cancelled_by: Optional[str] = None
        self.message: Optional[discord.Message] = None
        self.countdown_task: Optional[asyncio.Task] = None
        self.countdown_remaining = 0

    def get_money_offer(self, user_id: int) -> int:
        if user_id == self.user_a.id:
            return self.money_offer_a
        if user_id == self.user_b.id:
            return self.money_offer_b
        return 0

    def add_money_offer(self, user_id: int, amount: int) -> int:
        amount = int(amount)
        if user_id == self.user_a.id:
            self.money_offer_a = max(0, self.money_offer_a + amount)
            return self.money_offer_a
        if user_id == self.user_b.id:
            self.money_offer_b = max(0, self.money_offer_b + amount)
            return self.money_offer_b
        return 0

    def _format_offer_block(self, offer: Dict[str, int], money_offer: int) -> str:
        if not offer and money_offer <= 0:
            return "*No vehicles or coins added yet*"

        sorted_items = sorted(
            offer.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        lines = []
        if money_offer > 0:
            lines.append(f"\u2022 {format_money(money_offer)}")

        lines.extend(
            f"\u2022 {format_count(count)} | {display_vehicle_name(name)}"
            for name, count in sorted_items[:20]
        )
        if len(sorted_items) > 20:
            lines.append(f"...and {len(sorted_items) - 20} more")
        return "\n".join(lines)

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title="\U0001F91D Vehicle Trade", color=discord.Color.gold())

        embed.add_field(
            name=f"\U0001F381 {self.user_a.name}'s Offer",
            value=self._format_offer_block(self.offer_a, self.money_offer_a),
            inline=True,
        )
        embed.add_field(
            name=f"\U0001F381 {self.user_b.name}'s Offer",
            value=self._format_offer_block(self.offer_b, self.money_offer_b),
            inline=True,
        )

        status_a = "\u2705 READY" if self.ready_a else "\u231B WAITING"
        status_b = "\u2705 READY" if self.ready_b else "\u231B WAITING"
        status_text = f"**{self.user_a.name}:** {status_a}\n**{self.user_b.name}:** {status_b}"

        if self.countdown_remaining > 0:
            status_text += f"\n\n\u23F3 Completing in {self.countdown_remaining}s"

        embed.add_field(name="\U0001F4CB Status", value=status_text, inline=False)

        if self.cancelled:
            embed.title = "\u274C Trade Cancelled"
            if self.cancelled_by:
                embed.description = f"Reason: {self.cancelled_by}"
            embed.color = discord.Color.red()
        elif self.completed:
            embed.title = "\u2705 Trade Completed"
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

    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success, emoji="\u2705")
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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="\U0001F6AB")
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
        balances = load_balances()
        balance_a = _coerce_non_negative_int(balances.get(str(self.user_a.id), 0))
        balance_b = _coerce_non_negative_int(balances.get(str(self.user_b.id), 0))

        if balance_a < self.money_offer_a:
            channel = interaction.channel if interaction else self.message.channel
            await channel.send(f"Trade failed: {self.user_a.name} no longer has enough coins.")
            self.cancelled = True
            self.cancelled_by = f"{self.user_a.name} missing coins"
            await self.update_message()
            return

        if balance_b < self.money_offer_b:
            channel = interaction.channel if interaction else self.message.channel
            await channel.send(f"Trade failed: {self.user_b.name} no longer has enough coins.")
            self.cancelled = True
            self.cancelled_by = f"{self.user_b.name} missing coins"
            await self.update_message()
            return

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

        if self.money_offer_a > 0:
            balances[str(self.user_a.id)] = balance_a - self.money_offer_a
            balances[str(self.user_b.id)] = balance_b + self.money_offer_a
            balance_b = balances[str(self.user_b.id)]

        if self.money_offer_b > 0:
            balances[str(self.user_b.id)] = balance_b - self.money_offer_b
            balances[str(self.user_a.id)] = balances.get(str(self.user_a.id), 0) + self.money_offer_b

        inventories[str(self.user_a.id)] = inv_a
        inventories[str(self.user_b.id)] = inv_b
        save_inventories(inventories)
        save_balances(balances)

        self.completed = True
        await self.update_message()
        self.stop()


class MarketSearchModal(discord.ui.Modal, title="Search market"):
    query = discord.ui.TextInput(
        label="Vehicle name",
        placeholder="Example: m50, bismarck, fresh police heli",
        required=False,
        max_length=100,
    )

    def __init__(self, market_view: "ShopBuyView"):
        super().__init__()
        self.market_view = market_view

    async def on_submit(self, interaction: discord.Interaction):
        query = str(self.query.value or "").strip()
        view = ShopBuyView(self.market_view.viewer, query=query, page=0)
        view.message = self.market_view.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)


class MarketBuyModal(discord.ui.Modal, title="Buy market listing"):
    amount = discord.ui.TextInput(
        label="Amount to buy",
        placeholder="1",
        default="1",
        required=True,
        max_length=20,
    )

    def __init__(self, market_view: "ShopBuyView", listing_id: str):
        super().__init__()
        self.market_view = market_view
        self.listing_id = listing_id

    async def on_submit(self, interaction: discord.Interaction):
        if not await safe_defer(interaction, ephemeral=True):
            return

        parsed_amount = parse_count(str(self.amount.value))
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
            return

        ok, message = buy_market_listing(interaction.user.id, self.listing_id, parsed_amount)
        await safe_send(interaction, message, ephemeral=True)
        await self.market_view.refresh_message()


class MarketBuyButton(discord.ui.Button):
    def __init__(self, market_view: "ShopBuyView", listing_id: str, index_label: int):
        super().__init__(label=f"Buy {index_label}", style=discord.ButtonStyle.success, emoji=COIN_EMOJI)
        self.market_view = market_view
        self.listing_id = listing_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MarketBuyModal(self.market_view, self.listing_id))


class ShopBuyView(discord.ui.View):
    def __init__(self, viewer: discord.abc.User, query: str = "", page: int = 0):
        super().__init__(timeout=180)
        self.viewer = viewer
        self.query = query.strip()
        self.message: Optional[discord.Message] = None

        listings = self.filtered_listings()
        self.page_count = max(1, (len(listings) + SHOP_PAGE_SIZE - 1) // SHOP_PAGE_SIZE)
        self.page = min(max(0, page), self.page_count - 1)

        search_button = discord.ui.Button(label="Search", style=discord.ButtonStyle.primary)
        search_button.callback = self.search_callback
        self.add_item(search_button)

        clear_button = discord.ui.Button(
            label="Clear",
            style=discord.ButtonStyle.secondary,
            disabled=not self.query,
        )
        clear_button.callback = self.clear_callback
        self.add_item(clear_button)

        prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary, disabled=self.page <= 0)
        prev_button.callback = self.prev_callback
        self.add_item(prev_button)

        next_button = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.secondary,
            disabled=self.page >= self.page_count - 1,
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)

        for index, listing in enumerate(self.page_items(), start=1):
            self.add_item(MarketBuyButton(self, str(listing.get("id", "")), index))

    def filtered_listings(self) -> list[Dict[str, Any]]:
        return get_market_listings(viewer_id=self.viewer.id, include_own=False, query=self.query)

    def page_items(self) -> list[Dict[str, Any]]:
        listings = self.filtered_listings()
        start = self.page * SHOP_PAGE_SIZE
        return listings[start : start + SHOP_PAGE_SIZE]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer.id:
            await interaction.response.send_message("Only the person who opened this shop can use it.", ephemeral=True)
            return False
        return True

    async def refresh_message(self):
        if not self.message:
            return
        view = ShopBuyView(self.viewer, query=self.query, page=self.page)
        view.message = self.message
        try:
            await self.message.edit(embed=view.create_embed(), view=view)
        except Exception as error:
            print(f"Error refreshing shop buy view: {error}")

    async def search_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MarketSearchModal(self))

    async def clear_callback(self, interaction: discord.Interaction):
        view = ShopBuyView(self.viewer, query="", page=0)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def prev_callback(self, interaction: discord.Interaction):
        view = ShopBuyView(self.viewer, query=self.query, page=self.page - 1)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def next_callback(self, interaction: discord.Interaction):
        view = ShopBuyView(self.viewer, query=self.query, page=self.page + 1)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    def create_embed(self) -> discord.Embed:
        listings = self.filtered_listings()
        title = "Vehicle Market"
        if self.query:
            title += f" - search: {escape(self.query)}"
        embed = discord.Embed(title=title, color=discord.Color.gold())
        embed.set_footer(
            text=(
                f"Balance: {format_money(get_user_balance(self.viewer.id))} | "
                f"Listings: {format_count(len(listings))} | Page {self.page + 1}/{self.page_count}"
            )
        )

        if not listings:
            embed.description = "No market listings found."
            return embed

        vehicles = get_vehicle_map()
        lines = []
        for index, listing in enumerate(self.page_items(), start=1):
            vehicle_name = str(listing.get("vehicle_name", ""))
            rarity = str(vehicles.get(vehicle_name, {}).get("rarity", "common")).lower()
            fresh_text = "Fresh" if listing.get("is_fresh") else "Normal"
            lines.append(
                "\n".join(
                    [
                        f"**{index}. {get_listing_display_name(listing)}**",
                        f"Rarity: **{display_rarity_name(rarity)}** | Type: **{fresh_text}**",
                        f"Price: **{format_price(listing.get('price', 0))} each** | Amount: **{format_count(listing.get('count', 0))}**",
                        f"Seller: <@{listing.get('seller_id')}> | ID: `{listing.get('id')}`",
                    ]
                )
            )
        embed.description = "\n\n".join(lines)
        return embed


class MarketSellModal(discord.ui.Modal, title="List vehicle on market"):
    vehicle_name = discord.ui.TextInput(
        label="Vehicle name",
        placeholder="Example: m50 or fresh m50",
        required=True,
        max_length=100,
    )
    amount = discord.ui.TextInput(
        label="Amount to list",
        placeholder="1",
        default="1",
        required=True,
        max_length=20,
    )
    price = discord.ui.TextInput(
        label="Price per vehicle",
        placeholder="Example: 250",
        required=True,
        max_length=20,
    )

    def __init__(self, sell_view: "ShopSellView"):
        super().__init__()
        self.sell_view = sell_view

    async def on_submit(self, interaction: discord.Interaction):
        if not await safe_defer(interaction, ephemeral=True):
            return

        parsed_amount = parse_count(str(self.amount.value))
        parsed_price = parse_count(str(self.price.value))
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
            return
        if parsed_price is None or parsed_price <= 0:
            await safe_send(interaction, "Invalid price. Enter a positive coin price.", ephemeral=True)
            return

        matched_vehicle = match_user_available_vehicle(interaction.user.id, str(self.vehicle_name.value))
        if not matched_vehicle:
            await safe_send(interaction, f"No available vehicle matching '{self.vehicle_name.value}' found.", ephemeral=True)
            return

        available_count = get_available_vehicle_counts_for_user(interaction.user.id).get(matched_vehicle, 0)
        if parsed_amount > available_count:
            await safe_send(
                interaction,
                f"You only have {format_count(available_count)} available {display_vehicle_name(matched_vehicle)}.",
                ephemeral=True,
            )
            return

        ok, message, _ = create_market_listing(interaction.user.id, matched_vehicle, parsed_amount, parsed_price)
        await safe_send(interaction, message, ephemeral=True)
        await self.sell_view.refresh_message()


class BaseSellModal(discord.ui.Modal, title="Sell for base price"):
    vehicle_name = discord.ui.TextInput(
        label="Vehicle name",
        placeholder="Example: m50 or fresh m50",
        required=True,
        max_length=100,
    )
    amount = discord.ui.TextInput(
        label="Amount to sell",
        placeholder="1",
        default="1",
        required=True,
        max_length=20,
    )

    def __init__(self, sell_view: "ShopSellView"):
        super().__init__()
        self.sell_view = sell_view

    async def on_submit(self, interaction: discord.Interaction):
        if not await safe_defer(interaction, ephemeral=True):
            return

        parsed_amount = parse_count(str(self.amount.value))
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
            return

        matched_vehicle = match_user_available_vehicle(interaction.user.id, str(self.vehicle_name.value))
        if not matched_vehicle:
            await safe_send(interaction, f"No available vehicle matching '{self.vehicle_name.value}' found.", ephemeral=True)
            return

        _ok, message = sell_vehicle_to_shop(interaction.user.id, matched_vehicle, parsed_amount)
        await safe_send(interaction, message, ephemeral=True)
        await self.sell_view.refresh_message()


class ShopSellView(discord.ui.View):
    def __init__(self, viewer: discord.abc.User):
        super().__init__(timeout=180)
        self.viewer = viewer
        self.message: Optional[discord.Message] = None

        market_button = discord.ui.Button(label="Market Listing", style=discord.ButtonStyle.primary, emoji=COIN_EMOJI)
        market_button.callback = self.market_callback
        self.add_item(market_button)

        base_button = discord.ui.Button(label="Base Price", style=discord.ButtonStyle.success)
        base_button.callback = self.base_callback
        self.add_item(base_button)

        listings_button = discord.ui.Button(label="My Listings", style=discord.ButtonStyle.secondary)
        listings_button.callback = self.my_listings_callback
        self.add_item(listings_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer.id:
            await interaction.response.send_message("Only the person who opened this shop can use it.", ephemeral=True)
            return False
        return True

    async def refresh_message(self):
        if not self.message:
            return
        view = ShopSellView(self.viewer)
        view.message = self.message
        try:
            await self.message.edit(embed=view.create_embed(), view=view)
        except Exception as error:
            print(f"Error refreshing shop sell view: {error}")

    async def market_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(MarketSellModal(self))

    async def base_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BaseSellModal(self))

    async def my_listings_callback(self, interaction: discord.Interaction):
        view = MyListingsView(self.viewer)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    def create_embed(self) -> discord.Embed:
        available = get_available_vehicle_counts_for_user(self.viewer.id)
        own_listings = get_market_listings(seller_id=self.viewer.id, include_own=True)
        embed = discord.Embed(title="Sell Vehicles", color=discord.Color.green())
        embed.description = (
            "**Market Listing** lets you choose your own price and wait for another player to buy.\n"
            f"**Base Price** sells instantly for {format_price(SELL_VEHICLE_PRICE)} each."
        )
        embed.set_footer(
            text=(
                f"Balance: {format_money(get_user_balance(self.viewer.id))} | "
                f"Available stacks: {format_count(len(available))} | "
                f"Market listings: {format_count(len(own_listings))}"
            )
        )
        return embed


class CancelListingButton(discord.ui.Button):
    def __init__(self, listings_view: "MyListingsView", listing_id: str, index_label: int):
        super().__init__(label=f"Cancel {index_label}", style=discord.ButtonStyle.danger)
        self.listings_view = listings_view
        self.listing_id = listing_id

    async def callback(self, interaction: discord.Interaction):
        if not await safe_defer(interaction, ephemeral=True):
            return
        ok, message = cancel_market_listing(interaction.user.id, self.listing_id)
        await safe_send(interaction, message, ephemeral=True)
        await self.listings_view.refresh_message()


class MyListingsView(discord.ui.View):
    def __init__(self, viewer: discord.abc.User, page: int = 0):
        super().__init__(timeout=180)
        self.viewer = viewer
        self.message: Optional[discord.Message] = None
        listings = self.filtered_listings()
        self.page_count = max(1, (len(listings) + SHOP_PAGE_SIZE - 1) // SHOP_PAGE_SIZE)
        self.page = min(max(0, page), self.page_count - 1)

        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_callback
        self.add_item(back_button)

        prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary, disabled=self.page <= 0)
        prev_button.callback = self.prev_callback
        self.add_item(prev_button)

        next_button = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.secondary,
            disabled=self.page >= self.page_count - 1,
        )
        next_button.callback = self.next_callback
        self.add_item(next_button)

        for index, listing in enumerate(self.page_items(), start=1):
            self.add_item(CancelListingButton(self, str(listing.get("id", "")), index))

    def filtered_listings(self) -> list[Dict[str, Any]]:
        return get_market_listings(seller_id=self.viewer.id, include_own=True)

    def page_items(self) -> list[Dict[str, Any]]:
        listings = self.filtered_listings()
        start = self.page * SHOP_PAGE_SIZE
        return listings[start : start + SHOP_PAGE_SIZE]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer.id:
            await interaction.response.send_message("Only the person who opened this shop can use it.", ephemeral=True)
            return False
        return True

    async def refresh_message(self):
        if not self.message:
            return
        view = MyListingsView(self.viewer, page=self.page)
        view.message = self.message
        try:
            await self.message.edit(embed=view.create_embed(), view=view)
        except Exception as error:
            print(f"Error refreshing my listings view: {error}")

    async def back_callback(self, interaction: discord.Interaction):
        view = ShopSellView(self.viewer)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def prev_callback(self, interaction: discord.Interaction):
        view = MyListingsView(self.viewer, page=self.page - 1)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    async def next_callback(self, interaction: discord.Interaction):
        view = MyListingsView(self.viewer, page=self.page + 1)
        view.message = self.message
        await interaction.response.edit_message(embed=view.create_embed(), view=view)

    def create_embed(self) -> discord.Embed:
        listings = self.filtered_listings()
        embed = discord.Embed(title="My Market Listings", color=discord.Color.green())
        embed.set_footer(text=f"Listings: {format_count(len(listings))} | Page {self.page + 1}/{self.page_count}")

        if not listings:
            embed.description = "You have no active market listings."
            return embed

        vehicles = get_vehicle_map()
        lines = []
        for index, listing in enumerate(self.page_items(), start=1):
            vehicle_name = str(listing.get("vehicle_name", ""))
            rarity = str(vehicles.get(vehicle_name, {}).get("rarity", "common")).lower()
            fresh_text = "Fresh" if listing.get("is_fresh") else "Normal"
            lines.append(
                "\n".join(
                    [
                        f"**{index}. {get_listing_display_name(listing)}**",
                        f"Rarity: **{display_rarity_name(rarity)}** | Type: **{fresh_text}**",
                        f"Price: **{format_price(listing.get('price', 0))} each** | Amount: **{format_count(listing.get('count', 0))}**",
                        f"ID: `{listing.get('id')}`",
                    ]
                )
            )
        embed.description = "\n\n".join(lines)
        return embed


def get_available_vehicle_counts_for_user(user_id: int) -> Dict[str, int]:
    active_trade = get_active_trade_for_user(user_id)
    active_offer = get_trade_offer_for_user(active_trade, user_id) if active_trade else None
    return get_available_vehicle_counts(user_id, active_offer)


def match_user_available_vehicle(user_id: int, query: str) -> Optional[str]:
    available = get_available_vehicle_counts_for_user(user_id)
    query = str(query or "").strip()
    if not query:
        return None
    if query in available:
        return query

    normalized_query = normalize_name(query)
    if normalized_query.startswith("fresh"):
        trimmed_query = query.strip()[5:].strip(" :-_")
        matched_base = find_best_vehicle_match(
            [split_inventory_key(name)[0] for name in available.keys()],
            trimmed_query,
        )
        if matched_base:
            fresh_key = make_inventory_key(matched_base, True)
            if fresh_key in available:
                return fresh_key

    return find_best_vehicle_match(available.keys(), query)


def build_available_vehicle_choices(user_id: int, current: str) -> list[app_commands.Choice[str]]:
    available = get_available_vehicle_counts_for_user(user_id)
    current_lower = str(current or "").lower()

    sorted_items = sorted(
        available.items(),
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
        or current_lower in display_vehicle_name(name).lower().replace(" ", "_")
    ][:25]


def register_trade_commands(discord_bot: commands.Bot):
    @discord_bot.tree.command(name="inventory", description="View a vehicle inventory")
    @app_commands.describe(user="The user whose inventory you want to view")
    async def inventory_slash(interaction: discord.Interaction, user: Optional[discord.User] = None):
        target_user = user or interaction.user
        view = InventoryOverview(target_user, interaction.user)
        await interaction.response.send_message(embed=create_overview_embed(target_user), view=view)

    @discord_bot.tree.command(name="shop", description="Open the vehicle coin shop")
    @app_commands.guild_only()
    @app_commands.describe(
        action="Buy from the market or sell your vehicles",
        sell_type="Use market to list for players, or base_price to sell instantly to the shop",
        vehicle="Vehicle to sell",
        amount="Amount to sell",
        price="Market price per vehicle. Only used with sell_type: market",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="buy", value="buy"),
            app_commands.Choice(name="sell", value="sell"),
        ],
        sell_type=[
            app_commands.Choice(name="market", value="market"),
            app_commands.Choice(name="shop (base price)", value="base_price"),
        ],
    )
    async def shop_slash(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        sell_type: Optional[str] = None,
        vehicle: Optional[str] = None,
        amount: Optional[str] = None,
        price: Optional[str] = None,
    ):
        selected_action = str(action.value).lower()
        if selected_action == "buy":
            if sell_type or vehicle or amount or price:
                await safe_send(
                    interaction,
                    "Sell type, vehicle, amount, and price are only used with `/shop sell`.",
                    ephemeral=True,
                )
                return

            view = ShopBuyView(interaction.user)
            await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
            try:
                view.message = await interaction.original_response()
            except Exception as error:
                print(f"Error storing shop buy message: {error}")
            return

        selected_sell_type = str(sell_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        if selected_sell_type in {"shop", "base", "baseprice"}:
            selected_sell_type = "base_price"

        direct_values = [vehicle, amount, price]
        has_direct_sell = any(value not in (None, "") for value in direct_values)
        if has_direct_sell or selected_sell_type:
            if not selected_sell_type:
                selected_sell_type = "market"

            if selected_sell_type not in {"market", "base_price"}:
                await safe_send(interaction, "Choose `market` or `base_price` for the sell type.", ephemeral=True)
                return

            if selected_sell_type == "market" and (not vehicle or not amount or not price):
                await safe_send(
                    interaction,
                    "For market selling, use `/shop sell sell_type:market vehicle:<name> amount:<amount> price:<price>`.",
                    ephemeral=True,
                )
                return

            if selected_sell_type == "base_price":
                if not vehicle or not amount:
                    await safe_send(
                        interaction,
                        "For base price selling, use `/shop sell sell_type:base_price vehicle:<name> amount:<amount>`.",
                        ephemeral=True,
                    )
                    return
                if price:
                    await safe_send(
                        interaction,
                        f"Do not set a price for base price selling. The shop pays {format_price(SELL_VEHICLE_PRICE)} each.",
                        ephemeral=True,
                    )
                    return

            if not await safe_defer(interaction, ephemeral=True):
                return

            parsed_amount = parse_count(amount)
            if parsed_amount is None or parsed_amount <= 0:
                await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
                return

            matched_vehicle = match_user_available_vehicle(interaction.user.id, vehicle)
            if not matched_vehicle:
                await safe_send(interaction, f"No available vehicle matching '{vehicle}' found.", ephemeral=True)
                return

            if selected_sell_type == "base_price":
                _ok, message = sell_vehicle_to_shop(interaction.user.id, matched_vehicle, parsed_amount)
                await safe_send(interaction, message, ephemeral=True)
                return

            parsed_price = parse_count(price)
            if parsed_price is None or parsed_price <= 0:
                await safe_send(interaction, "Invalid price. Enter a positive coin price.", ephemeral=True)
                return

            ok, message, _ = create_market_listing(interaction.user.id, matched_vehicle, parsed_amount, parsed_price)
            await safe_send(interaction, message, ephemeral=True)
            return

        view = ShopSellView(interaction.user)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except Exception as error:
            print(f"Error storing shop sell message: {error}")

    @shop_slash.autocomplete("vehicle")
    async def shop_vehicle_autocomplete(interaction: discord.Interaction, current: str):
        namespace = getattr(interaction, "namespace", None)
        action_value = getattr(getattr(namespace, "action", None), "value", getattr(namespace, "action", None))
        if str(action_value or "").lower() != "sell":
            return []
        return build_available_vehicle_choices(interaction.user.id, current)

    @discord_bot.tree.command(name="tradeadd", description="Add a vehicle or coins to your active trade offer")
    @app_commands.guild_only()
    @app_commands.describe(item="Vehicle or coins to add", amount="How many vehicles or coins")
    async def tradeadd_slash(interaction: discord.Interaction, item: str, amount: str = "1"):
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

        if is_money_trade_item(item):
            current_money_offer = trade_view.get_money_offer(interaction.user.id)
            available_money = get_user_balance(interaction.user.id) - current_money_offer
            if parsed_amount > available_money:
                await safe_send(
                    interaction,
                    f"You do not have enough coins. Available: {format_money(max(0, available_money))}",
                    ephemeral=True,
                )
                return

            trade_view.add_money_offer(interaction.user.id, parsed_amount)
            trade_view.reset_countdown()
            await trade_view.update_message()
            await safe_send(
                interaction,
                f"Added **{format_money(parsed_amount)}** to your offer.",
                ephemeral=True,
            )
            return

        available_vehicles = get_trade_available_vehicles(interaction.user.id)
        matched_vehicle = item if item in available_vehicles else find_best_vehicle_match(available_vehicles.keys(), item)
        if not matched_vehicle:
            await safe_send(interaction, f"No vehicle matching '{item}' found in your inventory.", ephemeral=True)
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

    @tradeadd_slash.autocomplete("item")
    async def tradeadd_item_autocomplete(interaction: discord.Interaction, current: str):
        trade_view = get_active_trade_for_user(interaction.user.id)
        available_vehicles = get_trade_available_vehicles(interaction.user.id)
        current_lower = current.lower()
        choices = []

        if (
            not current_lower
            or "money".startswith(current_lower)
            or "coins".startswith(current_lower)
            or current_lower in {"$", "cash"}
        ):
            current_money_offer = trade_view.get_money_offer(interaction.user.id) if trade_view else 0
            available_money = max(0, get_user_balance(interaction.user.id) - current_money_offer)
            choices.append(
                app_commands.Choice(
                    name=f"Coins ({format_money(available_money)} available)",
                    value="money",
                )
            )

        sorted_items = sorted(
            available_vehicles.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        choices.extend(
            app_commands.Choice(
                name=f"{display_vehicle_name(name)} ({format_count(count)} owned)",
                value=name,
            )
            for name, count in sorted_items
            if not current_lower
            or current_lower in name.lower()
            or current_lower in display_vehicle_name(name).lower()
        )
        return choices[:25]

    @discord_bot.tree.command(name="traderemove", description="Remove a vehicle or coins from your active trade offer")
    @app_commands.guild_only()
    @app_commands.describe(item="Vehicle or coins to remove", amount="How many vehicles or coins")
    async def traderemove_slash(interaction: discord.Interaction, item: str, amount: str = "1"):
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
        current_money_offer = trade_view.get_money_offer(interaction.user.id)
        if not current_offer and current_money_offer <= 0:
            await safe_send(interaction, "Your offer is empty.", ephemeral=True)
            return

        parsed_amount = parse_count(amount)
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Enter a positive number.", ephemeral=True)
            return

        if is_money_trade_item(item):
            if current_money_offer <= 0:
                await safe_send(interaction, "You do not have coins in your current offer.", ephemeral=True)
                return

            amount_to_remove = min(parsed_amount, current_money_offer)
            trade_view.add_money_offer(interaction.user.id, -amount_to_remove)
            trade_view.reset_countdown()
            await trade_view.update_message()
            await safe_send(
                interaction,
                f"Removed **{format_money(amount_to_remove)}** from your offer.",
                ephemeral=True,
            )
            return

        matched_vehicle = item if item in current_offer else find_best_vehicle_match(current_offer.keys(), item)
        if not matched_vehicle:
            await safe_send(interaction, f"No vehicle matching '{item}' found in your current offer.", ephemeral=True)
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

    @traderemove_slash.autocomplete("item")
    async def traderemove_item_autocomplete(interaction: discord.Interaction, current: str):
        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            return []

        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id) or {}
        current_lower = current.lower()
        choices = []

        current_money_offer = trade_view.get_money_offer(interaction.user.id)
        if current_money_offer > 0 and (
            not current_lower
            or "money".startswith(current_lower)
            or "coins".startswith(current_lower)
            or current_lower in {"$", "cash"}
        ):
            choices.append(
                app_commands.Choice(
                    name=f"Coins ({format_money(current_money_offer)} in offer)",
                    value="money",
                )
            )

        sorted_items = sorted(
            current_offer.items(),
            key=lambda item: (-item[1], display_vehicle_name(item[0]).lower()),
        )

        choices.extend(
            app_commands.Choice(
                name=f"{display_vehicle_name(name)} ({format_count(count)} in offer)",
                value=name,
            )
            for name, count in sorted_items
            if not current_lower
            or current_lower in name.lower()
            or current_lower in display_vehicle_name(name).lower()
        )
        return choices[:25]

    @discord_bot.tree.command(name="trade", description="Send a trade request to another user")
    @app_commands.guild_only()
    @app_commands.describe(user="The user you want to trade with")
    async def trade_slash(interaction: discord.Interaction, user: discord.User):
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
                f"\U0001F91D Trade started between {user.mention} and {interaction.user.mention}.\n"
                "Use `/tradeadd` to add vehicles or coins and `/traderemove` to remove them.",
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
            public_comment = wrong_guess_comments_are_public(self.view.guild_id)
            await interaction.response.send_message(
                f"{interaction.user.mention} wrong name.",
                ephemeral=not public_comment,
            )
            return

        self.view.caught = True
        display_code = (
            self.vehicle_code.split(",")[0].strip()
            if isinstance(self.vehicle_code, str)
            else str(self.vehicle_code)
        )

        caught_label = display_vehicle_name(self.correct_name)
        awarded_fresh = self.view.is_fresh
        catch_emojis = []
        if self.view.rarity == "specials":
            catch_emojis.append(SPECIAL_CATCH_EMOJI)
        if awarded_fresh:
            catch_emojis.append(FRESH_CATCH_EMOJI)
        catch_status_emoji = f"{' '.join(catch_emojis)} " if catch_emojis else ""
        if awarded_fresh:
            caught_label = f"{caught_label} [Fresh]"

        reward = get_catch_reward(self.view.rarity, awarded_fresh)
        if reward > 0:
            add_money(interaction.user.id, reward)
        reward_text = f" and earned **{format_money(reward)}**" if reward > 0 else ""

        await interaction.response.send_message(
            f"\U0001F389 {catch_status_emoji}{interaction.user.mention} caught **{caught_label}** (`{display_code}`){reward_text}",
            ephemeral=False,
        )
        add_to_inventory(interaction.user.id, self.correct_name, is_fresh=awarded_fresh)

        await self.view.update_all_messages(
            f"\U0001F3C1 Captured by {interaction.user.name}: {caught_label}",
            concluded=True,
        )
        self.view.stop()


class CatchView(discord.ui.View):
    def __init__(
        self,
        vehicle_name: str,
        vehicle_code: str,
        image_url: str,
        rarity: str,
        is_fresh: bool = False,
        *,
        guild_id: Optional[int] = None,
        spawn_mode: str = "normal",
        timeout_seconds: int = SPAWN_DESPAWN_SECONDS,
    ):
        super().__init__(timeout=timeout_seconds)
        self.vehicle_name = vehicle_name
        self.vehicle_code = vehicle_code
        self.image_url = image_url
        self.rarity = rarity.lower()
        self.is_fresh = is_fresh
        self.guild_id = guild_id
        self.spawn_mode = spawn_mode
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.caught = False
        self.messages: list[discord.Message] = []
        self.header = SPAWN_HEADER
        self.hue = 0.0 if self.rarity in {"exotic", "specials"} else None
        if self.rarity == "specials":
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.style = discord.ButtonStyle.secondary
                    item.emoji = SPECIAL_CATCH_EMOJI

    def add_message(self, message: discord.Message):
        self.messages.append(message)

    def build_embed(
        self,
        *,
        color: Optional[discord.Color] = None,
        concluded: bool = False,
    ) -> discord.Embed:
        if color is None:
            color = discord.Color(RARITY_COLORS.get(self.rarity, 0x0000FF))

        embed = discord.Embed(title=self.header, color=color)
        description_lines = []
        if self.spawn_mode == "event":
            description_lines.append(EVENT_SPAWN_LABEL)
        if description_lines:
            embed.description = "\n".join(f"- {line}" for line in description_lines)
        embed.set_image(url=self.image_url)
        return embed

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

        embed = self.build_embed(color=color, concluded=concluded or self.caught)

        for message in self.messages:
            try:
                await message.edit(content=None, embed=embed, view=self)
            except Exception:
                continue

    def stop(self):
        unregister_active_spawn(self)
        super().stop()

    async def on_timeout(self):
        if not self.caught:
            await self.update_all_messages(DESPAWN_HEADER, concluded=True)
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
    fresh_spawn_chance: float = FRESH_SPAWN_CHANCE,
    rarity_weights: Optional[Dict[str, float]] = None,
    spawn_mode: str = "normal",
    replace_same_mode: bool = True,
    despawn_seconds: Optional[int] = None,
) -> bool:
    if not vehicles:
        if ctx:
            await ctx.send("No vehicles available.")
        return False

    target_guild = guild or (ctx.guild if ctx else None)

    if target_guild and replace_same_mode:
        await expire_active_spawns(target_guild.id, spawn_mode=spawn_mode)

    vehicle_name = get_random_vehicle(vehicles, rarity_weights=rarity_weights)
    if not vehicle_name:
        return False

    vehicle_data = vehicles[vehicle_name]
    local_path = vehicle_data.get("local_path")
    image_url = vehicle_data.get("url")
    vehicle_code = vehicle_data.get("code") or vehicle_data.get("rarity", "common")
    rarity = str(vehicle_data.get("rarity", "common"))
    if force_is_fresh is None:
        is_fresh = random.random() < fresh_spawn_chance
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

    actual_despawn_seconds = despawn_seconds
    if actual_despawn_seconds is None:
        actual_despawn_seconds = (
            EVENT_SPAWN_DESPAWN_SECONDS if spawn_mode == "event" else SPAWN_DESPAWN_SECONDS
        )

    print(
        f"Spawning vehicle: {vehicle_name} | rarity={rarity} | fresh={is_fresh} | "
        f"mode={spawn_mode} | timeout={actual_despawn_seconds}s | "
        f"remote={bool(is_http_url(image_url))} | local={bool(local_path)}"
    )

    view = CatchView(
        vehicle_name,
        str(vehicle_code),
        display_url,
        rarity,
        is_fresh=is_fresh,
        guild_id=target_guild.id if target_guild else None,
        spawn_mode=spawn_mode,
        timeout_seconds=actual_despawn_seconds,
    )

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

        embed = view.build_embed(color=discord.Color(RARITY_COLORS.get(rarity.lower(), 0x00FF00)))

        sender = ctx.send if ctx else channel.send
        sent = await sender(embed=embed, file=file, view=view)
        view.add_message(sent)
        remember_spawn_message(sent, view)
        register_active_spawn(view)
        return True
    except Exception as error:
        print(f"Error sending vehicle message: {error}")
        return False


async def spawn_in_guild(guild: discord.Guild):
    vehicles = get_vehicle_map()
    channel = _pick_spawn_channel(guild)

    if channel:
        await spawn_vehicle(vehicles, channel, guild=guild)
    else:
        print(f"No suitable channel found in {guild.name}")


def _known_vehicle_name(candidate: str) -> Optional[str]:
    candidate = str(candidate or "").strip()
    if not candidate:
        return None

    vehicles = get_vehicle_map()
    canonical_name = canonical_vehicle_name(candidate)
    if canonical_name in vehicles:
        return canonical_name

    return find_best_vehicle_match(vehicles.keys(), candidate)


def _vehicle_name_from_spawn_record(message_id: int) -> Optional[str]:
    record = load_spawn_records().get(str(message_id))
    if not record:
        return None

    vehicle_name = str(record.get("vehicle_name") or "").strip()
    return _known_vehicle_name(vehicle_name) or vehicle_name or None


def _vehicle_name_from_active_spawn(message_id: int) -> Optional[str]:
    prune_active_spawns()
    for views in active_spawns.values():
        for view in views:
            if any(spawn_message.id == message_id for spawn_message in view.messages):
                return _known_vehicle_name(view.vehicle_name) or view.vehicle_name
    return None


def _vehicle_name_from_text(text: str) -> Optional[str]:
    text = str(text or "").strip()
    if not text:
        return None

    candidates: list[str] = []
    caught_match = re.search(r"\*\*(.+?)\*\*", text)
    if caught_match:
        candidates.append(caught_match.group(1))

    if "Captured by" in text and ":" in text:
        candidates.append(text.split(":", 1)[1])

    for candidate in candidates:
        clean_candidate = re.sub(r"\s*\[Fresh\]\s*$", "", candidate.strip(), flags=re.IGNORECASE)
        known_name = _known_vehicle_name(clean_candidate)
        if known_name:
            return known_name

    return None


def _vehicle_name_from_message_embed(message: discord.Message) -> Optional[str]:
    vehicle_name = _vehicle_name_from_text(message.content)
    if vehicle_name:
        return vehicle_name

    for embed in message.embeds:
        for text in (
            embed.title or "",
            embed.description or "",
            embed.footer.text if embed.footer else "",
        ):
            vehicle_name = _vehicle_name_from_text(text)
            if vehicle_name:
                return vehicle_name

    return None


async def _fetch_message_for_check(source_message: discord.Message, message_id: int) -> Optional[discord.Message]:
    channels: list[Any] = []
    if hasattr(source_message.channel, "fetch_message"):
        channels.append(source_message.channel)

    if source_message.guild:
        source_channel_id = getattr(source_message.channel, "id", None)
        channels.extend(
            channel
            for channel in source_message.guild.text_channels
            if channel.id != source_channel_id
        )

    seen_channel_ids: set[int] = set()
    for channel in channels:
        channel_id = getattr(channel, "id", None)
        if channel_id in seen_channel_ids:
            continue
        if channel_id is not None:
            seen_channel_ids.add(channel_id)

        try:
            return await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            continue

    return None


async def resolve_spawn_message_vehicle_name(source_message: discord.Message, message_id: int) -> Optional[str]:
    vehicle_name = _vehicle_name_from_active_spawn(message_id)
    if vehicle_name:
        return vehicle_name

    vehicle_name = _vehicle_name_from_spawn_record(message_id)
    if vehicle_name:
        return vehicle_name

    fetched_message = await _fetch_message_for_check(source_message, message_id)
    if fetched_message:
        return _vehicle_name_from_message_embed(fetched_message)

    return None


async def spawn_event_wave(
    vehicles: Dict[str, Dict[str, Any]],
    channel: discord.abc.Messageable,
    *,
    guild: Optional[discord.Guild],
    count: int,
) -> int:
    successful_spawns = 0

    for index in range(count):
        spawned = await spawn_vehicle(
            vehicles,
            channel,
            guild=guild,
            rarity_weights=EVENT_RARITY_WEIGHTS,
            fresh_spawn_chance=EVENT_FRESH_SPAWN_CHANCE,
            spawn_mode="event",
            replace_same_mode=False,
        )
        if spawned:
            successful_spawns += 1

        if index < count - 1 and EVENT_SPAWN_DELAY_SECONDS > 0:
            await asyncio.sleep(EVENT_SPAWN_DELAY_SECONDS)

    return successful_spawns


@tasks.loop(seconds=5)
async def rainbow_task():
    update_tasks = []
    prune_active_spawns()

    for views in list(active_spawns.values()):
        for view in list(views):
            if view.is_finished() or view.caught or view.rarity not in {"exotic", "specials"} or not view.messages:
                continue

            palette = SPECIAL_RAINBOW_COLORS if view.rarity == "specials" else EXOTIC_RAINBOW_COLORS
            palette_index = int(view.hue if view.hue is not None else 0) % len(palette)
            color = discord.Color(palette[palette_index])
            update_tasks.append(view.update_all_messages(color=color))
            view.hue = (palette_index + 1) % len(palette)

    if update_tasks:
        await asyncio.gather(*update_tasks, return_exceptions=True)


def _bot_display_name() -> str:
    return WEBSITE_TITLE


def _bot_avatar_url() -> str:
    if not bot.user:
        return ""
    try:
        return str(bot.user.display_avatar.replace(size=512, static_format="png").url)
    except Exception:
        return str(bot.user.display_avatar.url)


def _client_id_from_token() -> str:
    token_prefix = TOKEN.split(".", 1)[0].strip()
    if not token_prefix:
        return ""

    try:
        padded_prefix = token_prefix + "=" * (-len(token_prefix) % 4)
        decoded = base64.urlsafe_b64decode(padded_prefix.encode("ascii")).decode("ascii")
    except Exception:
        return ""

    return decoded if decoded.isdigit() else ""


def _bot_client_id() -> str:
    if DISCORD_CLIENT_ID:
        return DISCORD_CLIENT_ID
    if bot.user:
        return str(bot.user.id)
    return _client_id_from_token()


def _bot_invite_url() -> str:
    client_id = _bot_client_id()
    if not client_id:
        return ""
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={client_id}"
        f"&permissions={INVITE_PERMISSIONS or '2147561408'}"
        "&scope=bot%20applications.commands"
    )


def _website_status_payload() -> Dict[str, Any]:
    vehicles = get_vehicle_map()
    total_vehicle_count, fresh_vehicle_count = get_global_inventory_totals(vehicles)
    ready = bot.is_ready()
    return {
        "online": bool(ready and not bot.is_closed()),
        "bot_name": _bot_display_name(),
        "guild_count": len(bot.guilds) if ready else 0,
        "vehicle_count": len(vehicles),
        "catalog_vehicle_count": len(vehicles),
        "total_vehicle_count": total_vehicle_count,
        "fresh_vehicle_count": fresh_vehicle_count,
        "last_update": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "invite_url": _bot_invite_url(),
        "avatar_url": _bot_avatar_url(),
        "server_invite_url": SERVER_INVITE_URL,
    }


def build_about_embed() -> discord.Embed:
    vehicles = get_vehicle_map()
    total_vehicle_count, _ = get_global_inventory_totals(vehicles)
    uptime_text = format_uptime(int(time.time()) - BOT_STARTED_AT)
    guild_count = len(bot.guilds) if bot.is_ready() else 0
    player_count = len(load_inventories())

    lines = [
        "Military Tycoon vehicle dex and inventory bot.",
        "Catch vehicles, trade, sell, and practice guessing.",
        "",
        f"*Running version **{BOT_VERSION}**.*",
        f"The bot has been online for **{uptime_text}**.",
        "",
        f"**{format_count(len(vehicles))}** vehicles to collect",
        f"**{format_count(total_vehicle_count)}** vehicles caught",
        f"**{format_count(player_count)}** players with inventories",
        f"**{format_count(guild_count)}** servers playing",
        "",
        f"This instance is owned by **{BOT_OWNER_NAME}**.",
    ]

    link_parts = []
    invite_url = _bot_invite_url()
    if invite_url:
        link_parts.append(f"[Invite me]({invite_url})")
    if SERVER_INVITE_URL:
        link_parts.append(f"[Discord server]({SERVER_INVITE_URL})")
    if SOURCE_CODE_URL:
        link_parts.append(f"[Source code]({SOURCE_CODE_URL})")
    if link_parts:
        lines.extend(["", " - ".join(link_parts)])

    policy_parts = []
    if TERMS_URL:
        policy_parts.append(f"[Terms of Service]({TERMS_URL})")
    if PRIVACY_URL:
        policy_parts.append(f"[Privacy Policy]({PRIVACY_URL})")
    if policy_parts:
        lines.append(" - ".join(policy_parts))

    embed = discord.Embed(
        title="Military Tycoon Vehicle Dex Bot",
        description="\n".join(lines),
        color=discord.Color.blue(),
    )
    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"discord.py {discord.__version__}")
    return embed


def _render_website() -> bytes:
    status = _website_status_payload()
    is_online = bool(status["online"])
    invite_url = str(status["invite_url"])
    server_invite_url = str(status.get("server_invite_url") or "")
    background_layer = (
        f'url("{escape(WEBSITE_BACKGROUND_URL)}") center / cover no-repeat,'
        if WEBSITE_BACKGROUND_URL
        else ""
    )
    invite_html = (
        f'<a class="button primary" href="{escape(invite_url)}" target="_blank" rel="noopener">Add to server</a>'
        if invite_url
        else '<span class="button primary disabled" title="Set DISCORD_CLIENT_ID if the bot is offline">Add to server</span>'
    )
    server_html = (
        f'<a class="button secondary" href="{escape(server_invite_url)}" target="_blank" rel="noopener">Join Discord</a>'
        if server_invite_url
        else ""
    )
    avatar_url = str(status.get("avatar_url") or "")
    profile_html = (
        f'<img class="profile" src="{escape(avatar_url)}" alt="Military Tycoon Dex logo">'
        if avatar_url
        else '<div class="profile fallback">MT<br>DEX</div>'
    )
    brand_icon_html = (
        f'<img class="brand-icon" src="{escape(avatar_url)}" alt="">'
        if avatar_url
        else '<span class="brand-mark">DEX</span>'
    )
    status_text = "Online" if is_online else "Offline"
    status_class = "online" if is_online else "offline"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Military Tycoon Vehicle Dex Bot</title>
  <style>
    :root {{
      color-scheme: dark;
      --black: #090b0a;
      --gunmetal: #151a18;
      --steel: #263238;
      --olive: #3d4a2b;
      --moss: #66713a;
      --sand: #c6aa72;
      --amber: #ff9d3d;
      --text: #f8f4e8;
      --muted: rgba(248, 244, 232, 0.84);
      --line: rgba(248, 244, 232, 0.28);
      --green: #54f08c;
      --red: #ff6578;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(90deg, rgba(5, 7, 5, 0.9), rgba(15, 20, 17, 0.56) 45%, rgba(5, 7, 5, 0.82)),
        {background_layer}
        radial-gradient(circle at 16% 72%, rgba(198, 170, 114, 0.28), transparent 30%),
        linear-gradient(135deg, #111714 0%, #263126 29%, #5b6335 48%, #997044 68%, #191e1d 100%);
      color: var(--text);
      overflow-x: hidden;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(118deg, transparent 0 12%, rgba(92, 102, 55, 0.35) 12% 24%, transparent 24% 37%, rgba(31, 39, 35, 0.45) 37% 51%, transparent 51% 64%, rgba(181, 142, 82, 0.2) 64% 75%, transparent 75%),
        linear-gradient(43deg, transparent 0 18%, rgba(10, 12, 11, 0.38) 18% 29%, transparent 29% 43%, rgba(76, 88, 48, 0.28) 43% 54%, transparent 54%);
      mix-blend-mode: soft-light;
    }}
    body::after {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(84, 240, 140, 0.12) 1px, transparent 1px),
        linear-gradient(90deg, rgba(84, 240, 140, 0.08) 1px, transparent 1px),
        linear-gradient(135deg, transparent 0 47%, rgba(255, 157, 61, 0.18) 48% 49%, transparent 50% 100%);
      background-size: 80px 80px, 80px 80px, 260px 260px;
      opacity: 0.48;
      mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.45), transparent 75%);
    }}
    .topbar {{
      position: relative;
      z-index: 2;
      min-height: 72px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      padding: 18px clamp(18px, 4vw, 46px);
      background: rgba(8, 11, 10, 0.72);
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(14px);
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--text);
      text-decoration: none;
      font-weight: 900;
      letter-spacing: 0;
    }}
    .brand-icon, .brand-mark {{
      width: 38px;
      height: 38px;
      object-fit: contain;
      border-radius: 50%;
    }}
    .brand-mark {{
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.08);
      font-size: 11px;
    }}
    main {{
      position: relative;
      z-index: 1;
      min-height: calc(100vh - 72px);
      display: grid;
      place-items: center;
      padding: clamp(34px, 6vw, 92px) clamp(18px, 5vw, 72px);
    }}
    h1 {{
      margin: 0;
      font-size: clamp(44px, 6vw, 82px);
      line-height: 1.05;
      letter-spacing: 0;
      text-shadow: 0 6px 28px rgba(0, 0, 0, 0.48);
    }}
    p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .hero {{
      width: min(1120px, 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: clamp(42px, 8vw, 98px);
    }}
    .profile-wrap {{
      flex: 0 1 430px;
      display: flex;
      justify-content: center;
      filter: drop-shadow(0 28px 44px rgba(0, 0, 0, 0.62));
    }}
    .profile {{
      width: min(430px, 42vw);
      max-width: 100%;
      aspect-ratio: 1;
      object-fit: contain;
      display: block;
    }}
    .profile.fallback {{
      border: 5px solid rgba(255, 255, 255, 0.85);
      border-radius: 50%;
      display: grid;
      place-items: center;
      text-align: center;
      font-size: 68px;
      font-weight: 900;
      line-height: 0.9;
      color: white;
      background: rgba(0, 0, 0, 0.18);
    }}
    .content {{
      flex: 1 1 420px;
      min-width: 0;
      padding: 28px 0;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 13px;
      font-weight: 700;
      white-space: nowrap;
      margin-bottom: 18px;
      background: rgba(9, 11, 10, 0.58);
      backdrop-filter: blur(10px);
    }}
    .dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--red);
    }}
    .status.online .dot {{ background: var(--green); }}
    .status.online {{ color: var(--green); }}
    .status.offline {{ color: var(--red); }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 9px;
      margin: 22px 0 28px;
    }}
    .metric {{
      border: 0;
      border-radius: 0;
      padding: 0;
      min-height: 0;
    }}
    .label {{
      color: var(--muted);
      font-size: 22px;
      margin-bottom: 0;
      display: inline;
      text-shadow: 0 4px 20px rgba(0, 0, 0, 0.38);
    }}
    .value {{
      font-size: 24px;
      font-weight: 900;
      overflow-wrap: anywhere;
      display: inline;
      color: #fff;
    }}
    .value.time {{
      font-size: 20px;
      line-height: 1.35;
    }}
    .actions {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .button {{
      appearance: none;
      border: 2px solid rgba(255, 255, 255, 0.88);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      color: var(--text);
      font-weight: 800;
      padding: 12px 28px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 220px;
      box-shadow: 0 18px 40px rgba(0, 0, 0, 0.25);
      backdrop-filter: blur(10px);
    }}
    .button.primary {{
      background: linear-gradient(135deg, rgba(255, 157, 61, 0.88), rgba(198, 170, 114, 0.72));
      color: #16130d;
      border-color: rgba(255, 226, 159, 0.9);
    }}
    .button.secondary {{
      background: rgba(12, 16, 14, 0.62);
    }}
    .button:hover {{
      transform: translateY(-1px);
      background: #fff;
      color: #151914;
    }}
    .button.disabled {{
      background: rgba(0, 0, 0, 0.12);
      color: rgba(255, 255, 255, 0.7);
    }}
    code {{
      color: var(--text);
      background: rgba(0, 0, 0, 0.18);
      border: 1px solid rgba(255, 255, 255, 0.25);
      border-radius: 6px;
      padding: 2px 6px;
    }}
    @media (max-width: 760px) {{
      .topbar {{
        align-items: center;
      }}
      main {{ padding: 28px; }}
      .hero {{
        flex-direction: column;
        gap: 28px;
        text-align: center;
      }}
      .profile {{ width: min(270px, 72vw); }}
      h1 {{ font-size: 42px; }}
      .actions {{ justify-content: center; }}
      .content {{ padding: 0; }}
      .button {{ min-width: min(280px, 100%); }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/">
      {brand_icon_html}
      <span>Military Tycoon Dex</span>
    </a>
  </header>
  <main>
    <section class="hero">
      <div class="profile-wrap">
        {profile_html}
      </div>
      <div class="content">
        <div class="status {status_class}" id="status-pill">
          <span class="dot"></span>
          <span id="status-text">{status_text}</span>
        </div>
        <h1>Military Tycoon Vehicle Dex Bot</h1>
        <section class="grid">
          <div class="metric">
            <span class="label">Serving </span>
            <span class="value" id="guild-count">{status["guild_count"]}</span>
            <span class="label"> servers</span>
          </div>
          <div class="metric">
            <span class="label">With </span>
            <span class="value" id="total-vehicle-count">{status["total_vehicle_count"]}</span>
            <span class="label"> total vehicles | </span>
            <span class="value" id="fresh-vehicle-count">{status["fresh_vehicle_count"]}</span>
            <span class="label"> fresh vehicles</span>
          </div>
          <div class="metric">
            <span class="label">Last update </span>
            <span class="value time" id="last-update">{escape(str(status["last_update"]))}</span>
          </div>
        </section>
        <section class="actions">
          {invite_html}
          {server_html}
        </section>
        <p>Use <code>/help</code></p>
      </div>
    </section>
  </main>
  <script>
    async function refreshStatus() {{
      try {{
        const res = await fetch('/status', {{ cache: 'no-store' }});
        if (!res.ok) return;
        const data = await res.json();
        const pill = document.getElementById('status-pill');
        const statusText = document.getElementById('status-text');
        pill.classList.toggle('online', Boolean(data.online));
        pill.classList.toggle('offline', !data.online);
        statusText.textContent = data.online ? 'Online' : 'Offline';
        document.getElementById('guild-count').textContent = data.guild_count;
        document.getElementById('total-vehicle-count').textContent = data.total_vehicle_count;
        document.getElementById('fresh-vehicle-count').textContent = data.fresh_vehicle_count;
        document.getElementById('last-update').textContent = data.last_update;
      }} catch (error) {{}}
    }}
    setInterval(refreshStatus, 15000);
  </script>
</body>
</html>"""
    return html.encode("utf-8")


def _form_value(form: Dict[str, list[str]], key: str, default: str = "") -> str:
    return (form.get(key, [default])[0] or default).strip()


def _parse_int_value(value: Any, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return default


def _dashboard_cookie_token(headers: Any) -> str:
    cookie_header = str(headers.get("Cookie") or "")
    for cookie in cookie_header.split(";"):
        name, separator, value = cookie.strip().partition("=")
        if separator and name == APPLICATION_DASHBOARD_COOKIE:
            return value.strip()
    return ""


def _dashboard_authorized(params: Dict[str, list[str]], headers: Any) -> bool:
    if not APPLICATION_DASHBOARD_TOKEN:
        return False
    candidates = [
        _form_value(params, "token"),
        _dashboard_cookie_token(headers),
    ]
    return any(candidate and hmac.compare_digest(candidate, APPLICATION_DASHBOARD_TOKEN) for candidate in candidates)


def _dashboard_url(guild_id: Optional[int] = None, notice: str = "") -> str:
    query = []
    if guild_id:
        query.append(f"guild_id={guild_id}")
    if notice:
        query.append(f"notice={quote(notice)}")
    return "/applications" + (f"?{'&'.join(query)}" if query else "")


def _dashboard_role_options(guild: discord.Guild, selected_role_id: int) -> str:
    options = [
        f'<option value="0"{"" if selected_role_id else " selected"}>No accepted role</option>'
    ]
    roles = [role for role in guild.roles if not role.is_default()]
    roles.sort(key=lambda role: role.position, reverse=True)
    for role in roles:
        selected = " selected" if role.id == selected_role_id else ""
        managed = " (managed)" if role.managed else ""
        options.append(
            f'<option value="{role.id}"{selected}>{escape(role.name)}{managed}</option>'
        )
    return "\n".join(options)


def _dashboard_channel_options(guild: discord.Guild, selected_channel_id: int, *, include_empty: bool = True) -> str:
    options = []
    if include_empty:
        options.append(f'<option value="0"{"" if selected_channel_id else " selected"}>Not set</option>')
    channels = sorted(
        guild.text_channels,
        key=lambda channel: ((channel.category.name if channel.category else ""), channel.position, channel.name.lower()),
    )
    for channel in channels:
        selected = " selected" if channel.id == selected_channel_id else ""
        category = f"{channel.category.name} / " if channel.category else ""
        options.append(
            f'<option value="{channel.id}"{selected}>{escape(category)}#{escape(channel.name)}</option>'
        )
    return "\n".join(options)


async def _dashboard_post_application_panel(guild_id: int, channel_id: int) -> str:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return "That server is not loaded by the bot."
    channel = await application_system.resolve_text_channel(guild, channel_id)
    if channel is None:
        return "That application channel was not found."
    missing_permissions = application_system.bot_channel_permission_errors(channel)
    if missing_permissions:
        return f"Cannot post in #{channel.name}. Missing: {', '.join(missing_permissions)}."

    guild_state = application_system.get_guild_state(guild.id)
    if not guild_state.get("panels"):
        return "Create at least one panel before posting."

    existing_message_id = int(guild_state.get("application_message_id") or 0)
    existing_channel_id = int(guild_state.get("application_channel_id") or 0)
    if existing_message_id and existing_channel_id == channel.id:
        try:
            message = await channel.fetch_message(existing_message_id)
            await message.edit(
                embed=application_system.build_application_panel_embed(guild),
                view=application_system.ApplicationSelectView(guild.id),
            )
            return f"Application panel updated in #{channel.name}."
        except discord.HTTPException:
            pass

    try:
        message = await channel.send(
            embed=application_system.build_application_panel_embed(guild),
            view=application_system.ApplicationSelectView(guild.id),
        )
    except discord.HTTPException as error:
        return f"Could not post panel: {truncate(error, 160)}"

    guild_state["application_channel_id"] = channel.id
    guild_state["application_message_id"] = message.id
    application_system.save_state()
    return f"Application panel posted in #{channel.name}."


def _run_dashboard_coro(coro: Any) -> str:
    if bot.loop.is_closed():
        return "Bot event loop is closed."
    try:
        return asyncio.run_coroutine_threadsafe(coro, bot.loop).result(timeout=30)
    except Exception as error:
        return f"Dashboard action failed: {truncate(error, 180)}"


def _dashboard_page(title: str, body: str) -> bytes:
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - Military Tycoon Dex</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0f0c;
      --panel: #171d18;
      --panel-2: #20271f;
      --line: rgba(245, 238, 216, 0.18);
      --text: #f7f1df;
      --muted: rgba(247, 241, 223, 0.72);
      --accent: #d1a85f;
      --green: #2ecc71;
      --red: #f45b69;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(135deg, rgba(11, 15, 12, .96), rgba(25, 33, 26, .88)),
        radial-gradient(circle at 18% 10%, rgba(209, 168, 95, .24), transparent 32%),
        radial-gradient(circle at 92% 14%, rgba(74, 95, 56, .38), transparent 30%);
      color: var(--text);
      min-height: 100vh;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px clamp(18px, 4vw, 44px);
      border-bottom: 1px solid var(--line);
      background: rgba(10, 13, 11, .72);
      position: sticky;
      top: 0;
      z-index: 10;
      backdrop-filter: blur(12px);
    }}
    main {{
      width: min(1220px, 100%);
      margin: 0 auto;
      padding: 26px clamp(14px, 3vw, 36px) 56px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; letter-spacing: 0; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    a {{ color: var(--accent); }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}
    .card {{
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02)), var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 20px 48px rgba(0,0,0,.28);
    }}
    .stack {{ display: grid; gap: 14px; }}
    .row {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
    label {{ display: block; font-weight: 700; font-size: 13px; color: var(--muted); margin-bottom: 6px; }}
    input, textarea, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #101510;
      color: var(--text);
      padding: 10px 11px;
      font: inherit;
    }}
    textarea {{ min-height: 84px; resize: vertical; }}
    button, .button {{
      border: 1px solid rgba(255,255,255,.2);
      border-radius: 7px;
      background: var(--accent);
      color: #10100c;
      padding: 10px 14px;
      font-weight: 900;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      justify-content: center;
      align-items: center;
      min-height: 40px;
    }}
    button.secondary, .button.secondary {{ background: #2d362d; color: var(--text); }}
    button.danger {{ background: var(--red); color: white; }}
    button.green {{ background: var(--green); color: #071007; }}
    .notice {{
      border: 1px solid rgba(209,168,95,.48);
      background: rgba(209,168,95,.12);
      color: #ffe0a1;
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 16px;
    }}
    .muted {{ color: var(--muted); }}
    .panel {{
      border: 1px solid var(--line);
      background: var(--panel-2);
      border-radius: 8px;
      padding: 14px;
      margin-top: 14px;
    }}
    .question {{
      border-left: 3px solid var(--accent);
      padding: 12px;
      background: rgba(0,0,0,.16);
      border-radius: 6px;
      margin-top: 10px;
    }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .three {{ display: grid; grid-template-columns: 1fr 1fr 140px; gap: 10px; align-items: end; }}
    .pill {{
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      color: var(--muted);
      font-size: 12px;
      gap: 6px;
    }}
    @media (max-width: 850px) {{
      .grid, .two, .three {{ grid-template-columns: 1fr; }}
      header {{ position: static; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <strong>Military Tycoon Dex</strong>
      <span class="pill">Application dashboard</span>
    </div>
    <a class="button secondary" href="/">Website</a>
  </header>
  <main>{body}</main>
</body>
</html>"""
    return html.encode("utf-8")


def _render_dashboard_login(error: str = "") -> bytes:
    if not APPLICATION_DASHBOARD_TOKEN:
        return _dashboard_page(
            "Dashboard disabled",
            """
            <section class="card">
              <h1>Application dashboard disabled</h1>
              <p>Set the <code>APPLICATION_DASHBOARD_TOKEN</code> environment variable on Render, then redeploy.</p>
            </section>
            """,
        )
    error_html = f'<div class="notice">{escape(error)}</div>' if error else ""
    return _dashboard_page(
        "Dashboard login",
        f"""
        <section class="card" style="max-width:520px;margin:8vh auto 0;">
          <h1>Application dashboard</h1>
          <p>Enter the private dashboard token to manage panels, questions, log channels, and accept roles.</p>
          {error_html}
          <form method="post" action="/applications">
            <input type="hidden" name="action" value="login">
            <label>Dashboard token</label>
            <input name="token" type="password" autocomplete="current-password" required>
            <div class="row" style="margin-top:14px;">
              <button type="submit">Open dashboard</button>
            </div>
          </form>
        </section>
        """,
    )


def _render_application_dashboard(params: Dict[str, list[str]]) -> bytes:
    if not bot.is_ready():
        return _dashboard_page("Dashboard", '<section class="card"><h1>Bot is starting</h1><p>Try again in a moment.</p></section>')

    guilds = sorted(bot.guilds, key=lambda item: item.name.lower())
    if not guilds:
        return _dashboard_page("Dashboard", '<section class="card"><h1>No servers loaded</h1><p>The bot is not in any servers yet.</p></section>')

    requested_guild_id = _parse_int_value(_form_value(params, "guild_id"), guilds[0].id)
    guild = bot.get_guild(requested_guild_id) or guilds[0]
    guild_state = application_system.get_guild_state(guild.id)
    panels = guild_state.setdefault("panels", {})
    selected_log_channel = int(guild_state.get("log_channel_id") or 0)
    selected_panel_channel = int(guild_state.get("application_channel_id") or 0)
    notice = _form_value(params, "notice")

    guild_options = "\n".join(
        f'<option value="{server.id}"{" selected" if server.id == guild.id else ""}>{escape(server.name)}</option>'
        for server in guilds
    )
    notice_html = f'<div class="notice">{escape(notice)}</div>' if notice else ""

    panel_blocks = []
    for panel_key, panel in sorted(panels.items()):
        questions = panel.get("questions") if isinstance(panel.get("questions"), list) else []
        enabled_checked = " checked" if panel.get("enabled", True) else ""
        accepted_role_id = int(panel.get("accepted_role_id") or 0)
        question_blocks = []
        for index, raw_question in enumerate(questions, start=1):
            question = application_system.normalize_question(raw_question)
            choice_text = ", ".join(question.get("options", [])) if question.get("type") == "select" else ""
            question_blocks.append(
                f"""
                <div class="question">
                  <form method="post" action="/applications">
                    <input type="hidden" name="action" value="edit_question">
                    <input type="hidden" name="guild_id" value="{guild.id}">
                    <input type="hidden" name="panel_key" value="{escape(panel_key)}">
                    <input type="hidden" name="question_number" value="{index}">
                    <label>Question {index}</label>
                    <textarea name="text" required>{escape(question.get("text", ""))}</textarea>
                    <label>Dropdown choices <span class="muted">(blank = text answer, comma separated = selection)</span></label>
                    <input name="choices" value="{escape(choice_text)}" placeholder="yes, no">
                    <div class="row" style="margin-top:10px;">
                      <button type="submit">Save question</button>
                    </div>
                  </form>
                  <form method="post" action="/applications">
                    <input type="hidden" name="action" value="delete_question">
                    <input type="hidden" name="guild_id" value="{guild.id}">
                    <input type="hidden" name="panel_key" value="{escape(panel_key)}">
                    <input type="hidden" name="question_number" value="{index}">
                    <div class="row" style="margin-top:8px;">
                      <button class="danger" type="submit">Delete</button>
                    </div>
                  </form>
                </div>
                """
            )

        panel_blocks.append(
            f"""
            <section class="panel">
              <form method="post" action="/applications">
                <input type="hidden" name="action" value="update_panel">
                <input type="hidden" name="guild_id" value="{guild.id}">
                <input type="hidden" name="panel_key" value="{escape(panel_key)}">
                <div class="two">
                  <div>
                    <label>Panel name</label>
                    <input name="name" value="{escape(panel.get("name", panel_key))}" required>
                  </div>
                  <div>
                    <label>Dropdown description</label>
                    <input name="description" value="{escape(panel.get("description", "Start this application."))}">
                  </div>
                </div>
                <div class="two" style="margin-top:10px;">
                  <div>
                    <label>Role given when accepted</label>
                    <select name="accepted_role_id">{_dashboard_role_options(guild, accepted_role_id)}</select>
                  </div>
                  <div>
                    <label>Open in dropdown</label>
                    <div class="row" style="min-height:40px;">
                      <input style="width:auto;" type="checkbox" name="enabled" value="1"{enabled_checked}>
                      <span class="muted">Users can start this application</span>
                    </div>
                  </div>
                </div>
                <div class="row" style="margin-top:12px;">
                  <button type="submit">Save panel</button>
                </div>
              </form>
              <form method="post" action="/applications">
                <input type="hidden" name="action" value="delete_panel">
                <input type="hidden" name="guild_id" value="{guild.id}">
                <input type="hidden" name="panel_key" value="{escape(panel_key)}">
                <div class="row" style="margin-top:8px;">
                  <button class="danger" type="submit">Delete panel</button>
                </div>
              </form>
              <h3 style="margin-top:18px;">Questions</h3>
              {''.join(question_blocks) if question_blocks else '<p>No questions yet.</p>'}
              <form class="card" style="margin-top:12px;box-shadow:none;" method="post" action="/applications">
                <input type="hidden" name="action" value="add_question">
                <input type="hidden" name="guild_id" value="{guild.id}">
                <input type="hidden" name="panel_key" value="{escape(panel_key)}">
                <div class="three">
                  <div>
                    <label>New question</label>
                    <input name="text" placeholder="Question text" required>
                  </div>
                  <div>
                    <label>Dropdown choices</label>
                    <input name="choices" placeholder="Leave blank, or: yes, no">
                  </div>
                  <div>
                    <label>Number</label>
                    <input name="question_number" type="number" min="1" value="{len(questions) + 1}">
                  </div>
                </div>
                <div class="row" style="margin-top:10px;">
                  <button type="submit">Add question</button>
                </div>
              </form>
            </section>
            """
        )

    body = f"""
    {notice_html}
    <div class="grid">
      <aside class="stack">
        <section class="card">
          <h2>Server</h2>
          <form method="get" action="/applications">
            <label>Choose server</label>
            <select name="guild_id" onchange="this.form.submit()">{guild_options}</select>
          </form>
        </section>
        <section class="card">
          <h2>Panel settings</h2>
          <form method="post" action="/applications">
            <input type="hidden" name="action" value="settings">
            <input type="hidden" name="guild_id" value="{guild.id}">
            <label>Panel text</label>
            <textarea name="panel_text">{escape(guild_state.get("panel_text") or application_system.DEFAULT_PANEL_TEXT)}</textarea>
            <label>Application log channel</label>
            <select name="log_channel_id">{_dashboard_channel_options(guild, selected_log_channel)}</select>
            <label>Application panel channel</label>
            <select name="application_channel_id">{_dashboard_channel_options(guild, selected_panel_channel)}</select>
            <div class="row" style="margin-top:12px;">
              <button type="submit">Save settings</button>
            </div>
          </form>
          <form method="post" action="/applications">
            <input type="hidden" name="action" value="post_panel">
            <input type="hidden" name="guild_id" value="{guild.id}">
            <div class="row" style="margin-top:8px;">
              <button class="green" type="submit">Post / update panel</button>
            </div>
          </form>
          <p class="muted">The bot needs Send Messages and Embed Links in those channels.</p>
        </section>
        <section class="card">
          <h2>Create panel</h2>
          <form method="post" action="/applications">
            <input type="hidden" name="action" value="create_panel">
            <input type="hidden" name="guild_id" value="{guild.id}">
            <label>Name</label>
            <input name="name" placeholder="Moderation team" required>
            <label>Description</label>
            <input name="description" placeholder="Apply for the moderation team">
            <div class="row" style="margin-top:12px;">
              <button type="submit">Create</button>
            </div>
          </form>
        </section>
      </aside>
      <section class="card">
        <h1>{escape(guild.name)} applications</h1>
        <p>Create panels, edit questions, add dropdown answers, and choose the role users get when accepted.</p>
        {''.join(panel_blocks) if panel_blocks else '<p>No panels yet. Create one on the left.</p>'}
      </section>
    </div>
    """
    return _dashboard_page("Application dashboard", body)


def _handle_application_dashboard_post(form: Dict[str, list[str]]) -> tuple[int, str, Optional[str]]:
    action = _form_value(form, "action")
    if action == "login":
        token = _form_value(form, "token")
        if APPLICATION_DASHBOARD_TOKEN and hmac.compare_digest(token, APPLICATION_DASHBOARD_TOKEN):
            return 302, _dashboard_url(), token
        return 401, "Wrong dashboard token.", None

    guild_id = _parse_int_value(_form_value(form, "guild_id"))
    guild = bot.get_guild(guild_id) if guild_id else None
    if guild is None:
        return 400, "Unknown server.", None
    guild_state = application_system.get_guild_state(guild.id)
    panels = guild_state.setdefault("panels", {})
    notice = "Saved."

    if action == "settings":
        guild_state["panel_text"] = _form_value(form, "panel_text", application_system.DEFAULT_PANEL_TEXT)[:1000]
        guild_state["log_channel_id"] = _parse_int_value(_form_value(form, "log_channel_id"))
        guild_state["application_channel_id"] = _parse_int_value(_form_value(form, "application_channel_id"))
    elif action == "post_panel":
        channel_id = _parse_int_value(_form_value(form, "application_channel_id")) or int(guild_state.get("application_channel_id") or 0)
        if not channel_id:
            notice = "Choose an application panel channel first."
        else:
            notice = _run_dashboard_coro(_dashboard_post_application_panel(guild.id, channel_id))
    elif action == "create_panel":
        name = _form_value(form, "name")[:100]
        panel_key = application_system.normalize_panel_key(name)
        if not panel_key:
            notice = "Panel name cannot be empty."
        elif panel_key in panels:
            notice = "That panel already exists."
        else:
            panels[panel_key] = {
                "name": name,
                "description": _form_value(form, "description", "Start this application.")[:100],
                "questions": [],
                "enabled": True,
                "accepted_role_id": None,
                "created_at": int(time.time()),
                "created_by": "dashboard",
            }
            notice = f"Created panel {panel_key}."
    elif action == "update_panel":
        panel_key = application_system.normalize_panel_key(_form_value(form, "panel_key"))
        panel = panels.get(panel_key)
        if not panel:
            notice = "Unknown panel."
        else:
            panel["name"] = _form_value(form, "name", panel_key)[:100]
            panel["description"] = _form_value(form, "description", "Start this application.")[:100]
            panel["enabled"] = "enabled" in form
            panel["accepted_role_id"] = _parse_int_value(_form_value(form, "accepted_role_id")) or None
            notice = f"Updated panel {panel_key}."
    elif action == "delete_panel":
        panel_key = application_system.normalize_panel_key(_form_value(form, "panel_key"))
        if panel_key in panels:
            del panels[panel_key]
            notice = f"Deleted panel {panel_key}."
        else:
            notice = "Unknown panel."
    elif action in {"add_question", "edit_question", "delete_question"}:
        panel_key = application_system.normalize_panel_key(_form_value(form, "panel_key"))
        panel = panels.get(panel_key)
        if not panel:
            notice = "Unknown panel."
        else:
            questions = panel.setdefault("questions", [])
            question_number = max(1, _parse_int_value(_form_value(form, "question_number"), len(questions) + 1))
            if action == "delete_question":
                if 1 <= question_number <= len(questions):
                    questions.pop(question_number - 1)
                    notice = "Question deleted and questions were renumbered."
                else:
                    notice = "That question number does not exist."
            else:
                text = _form_value(form, "text")[:300]
                if not text:
                    notice = "Question cannot be empty."
                else:
                    choices = _form_value(form, "choices")
                    parsed_choices = application_system.parse_question_choices(choices)
                    if parsed_choices is not None and len(parsed_choices) == 1:
                        notice = "Selection questions need at least 2 choices."
                    elif action == "add_question":
                        insert_index = min(max(0, question_number - 1), len(questions))
                        questions.insert(insert_index, application_system.make_question_value(text, choices))
                        notice = "Question added and questions were renumbered."
                    elif 1 <= question_number <= len(questions):
                        questions[question_number - 1] = application_system.make_question_value(text, choices, questions[question_number - 1])
                        notice = "Question updated."
                    else:
                        notice = "That question number does not exist."
    else:
        notice = "Unknown dashboard action."

    application_system.save_state()
    return 302, _dashboard_url(guild.id, notice), None


class _WebsiteHandler(BaseHTTPRequestHandler):
    def _send_body(self, status_code: int, body: bytes, content_type: str) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str, *, set_token_cookie: Optional[str] = None, clear_cookie: bool = False) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if set_token_cookie:
            self.send_header(
                "Set-Cookie",
                f"{APPLICATION_DASHBOARD_COOKIE}={set_token_cookie}; Path=/applications; "
                "HttpOnly; SameSite=Lax; Max-Age=2592000",
            )
        if clear_cookie:
            self.send_header(
                "Set-Cookie",
                f"{APPLICATION_DASHBOARD_COOKIE}=; Path=/applications; HttpOnly; SameSite=Lax; Max-Age=0",
            )
        self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query, keep_blank_values=True)

        if parsed_path.path.startswith("/applications/logout"):
            self._redirect("/applications", clear_cookie=True)
            return

        if parsed_path.path.startswith("/applications"):
            if not _dashboard_authorized(params, self.headers):
                body = _render_dashboard_login()
                self._send_body(200, body, "text/html; charset=utf-8")
                return

            token_from_url = _form_value(params, "token")
            if token_from_url and APPLICATION_DASHBOARD_TOKEN and hmac.compare_digest(token_from_url, APPLICATION_DASHBOARD_TOKEN):
                self._redirect(_dashboard_url(_parse_int_value(_form_value(params, "guild_id"))), set_token_cookie=token_from_url)
                return

            body = _render_application_dashboard(params)
            self._send_body(200, body, "text/html; charset=utf-8")
            return

        if self.path.startswith("/status"):
            payload = _website_status_payload()
            body = json.dumps(payload).encode("utf-8")
            self._send_body(200, body, "application/json; charset=utf-8")
            return

        if self.path.startswith("/invite"):
            invite_url = _bot_invite_url()
            if not invite_url:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Invite URL is not configured yet.")
                return
            self.send_response(302)
            self.send_header("Location", invite_url)
            self.end_headers()
            return

        if self.path.startswith("/discord") or self.path.startswith("/server"):
            if not SERVER_INVITE_URL:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Discord server URL is not configured yet.")
                return
            self.send_response(302)
            self.send_header("Location", SERVER_INVITE_URL)
            self.end_headers()
            return

        body = _render_website()
        self._send_body(200, body, "text/html; charset=utf-8")

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if not parsed_path.path.startswith("/applications"):
            self._send_body(404, b"Not Found", "text/plain; charset=utf-8")
            return

        try:
            content_length = min(int(self.headers.get("Content-Length", "0")), 262_144)
        except ValueError:
            content_length = 0
        form = parse_qs(
            self.rfile.read(content_length).decode("utf-8", errors="replace"),
            keep_blank_values=True,
        )
        action = _form_value(form, "action")
        if action != "login" and not _dashboard_authorized(form, self.headers):
            body = _render_dashboard_login("Please log in again.")
            self._send_body(401, body, "text/html; charset=utf-8")
            return

        status_code, result, token_cookie = _handle_application_dashboard_post(form)
        if status_code == 302:
            self._redirect(result, set_token_cookie=token_cookie)
            return

        body = _render_dashboard_login(result)
        self._send_body(status_code, body, "text/html; charset=utf-8")

    def log_message(self, format, *args):
        return


def start_website_server():
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
            server = HTTPServer(("0.0.0.0", port), _WebsiteHandler)
            print(f"Website server listening on port {port}")
            server.serve_forever()
        except Exception as error:
            print(f"Website server error: {error}")

    Thread(target=_serve, daemon=True).start()


async def set_ready_presence():
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="/help | https://dexbot-support.onrender.com"),
        )
        print("Presence set to online.")
    except Exception as error:
        print(f"Failed to set presence: {error}")


async def sync_all_commands():
    if COMMAND_SYNC_MODE == "guild":
        if not COMMAND_SYNC_GUILD_ID:
            raise RuntimeError("COMMAND_SYNC_MODE is set to 'guild' but COMMAND_SYNC_GUILD_ID is missing.")

        target_guild = discord.Object(id=COMMAND_SYNC_GUILD_ID)
        bot.tree.clear_commands(guild=target_guild)
        bot.tree.copy_global_to(guild=target_guild)
        synced = await bot.tree.sync(guild=target_guild)
        print(f"Guild-only synced {len(synced)} command(s) to guild {COMMAND_SYNC_GUILD_ID}.")
        return synced

    synced = await bot.tree.sync()
    print(f"Globally synced {len(synced)} command(s)")

    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Cleared guild-specific command copies in {guild.name}")
        except Exception as guild_error:
            print(f"Error clearing guild command copies in {guild.name}: {guild_error}")

    print(f"Sync complete. Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages.")
    return synced


register_trade_commands(bot)


@bot.tree.command(name="help", description="Show MT vehicle bot commands")
async def help_slash(interaction: discord.Interaction):
    await safe_send(interaction, build_help_message(), ephemeral=True)


@bot.tree.command(name="about", description="Show bot info, stats, and links")
async def about_slash(interaction: discord.Interaction):
    await safe_send(interaction, embed=build_about_embed())


@bot.tree.command(name="leaderboard", description="Show vehicle and coin leaderboards")
@app_commands.guild_only()
async def leaderboard_slash(interaction: discord.Interaction):
    if not await safe_defer(interaction):
        return

    view = LeaderboardView(interaction.user, "vehicles")
    embed = await create_leaderboard_embed(interaction.guild, interaction.user.id, "vehicles")
    await safe_send(interaction, embed=embed, view=view)

@bot.tree.command(name="show", description="Show a vehicle's picture and rarity")
@app_commands.describe(vehicle_name="The name of the vehicle to show")
async def show_vehicle(interaction: discord.Interaction, vehicle_name: str):
    vehicles = get_vehicle_map()
    matched_vehicle = vehicle_name if vehicle_name in vehicles else find_best_vehicle_match(vehicles.keys(), vehicle_name)

    if not matched_vehicle:
        await interaction.response.send_message(
            f"Vehicle **{vehicle_name.replace('-', '_')}** not found.",
            ephemeral=True,
        )
        return

    vehicle_data = vehicles[matched_vehicle]
    if not _vehicle_is_showable(vehicle_data):
        await interaction.response.send_message(
            "This vehicle has not been released yet.",
            ephemeral=True,
        )
        return

    rarity = str(vehicle_data.get("rarity", "common")).lower()
    local_path = vehicle_data.get("local_path")
    image_url = vehicle_data.get("url")
    regular_count, fresh_count = get_global_vehicle_counts(matched_vehicle)

    embed = discord.Embed(
        title=f"{display_vehicle_name(matched_vehicle)} ({display_rarity_name(rarity)})",
        color=discord.Color(RARITY_COLORS.get(rarity, 0x808080)),
    )
    embed.set_footer(text=f"Normal: {format_count(regular_count)} | Fresh: {format_count(fresh_count)}")

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
    vehicle_names = sorted(name for name, data in vehicles.items() if _vehicle_is_showable(data))

    return [
        app_commands.Choice(name=name.replace("-", "_"), value=name)
        for name in vehicle_names
        if not current_lower
        or current_lower in name.lower()
        or current_lower in name.lower().replace("-", "_")
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


@bot.tree.command(name="botcomment", description="Set whether wrong vehicle-name comments are public")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(public="True shows wrong-name comments to everyone. False shows them only to the guesser")
async def botcomment_slash(interaction: discord.Interaction, public: bool):
    if not interaction.guild:
        await safe_send(interaction, "This command can only be used in a server.", ephemeral=True)
        return

    if not interaction.permissions.manage_guild:
        await safe_send(interaction, "Only server admins can use this command.", ephemeral=True)
        return

    set_guild_bool_setting(interaction.guild.id, "bot_comment_public", public)
    visibility_text = "everyone" if public else "only the user who guessed"
    await safe_send(
        interaction,
        f"Wrong-name comments will now be shown to **{visibility_text}**.",
        ephemeral=True,
    )


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

    if command == "!help":
        return

    if command in {"!permadd", "!permremove"}:
        if message.author.id != PERMISSION_OWNER_USER_ID:
            return

        if len(parts) != 2:
            await message.channel.send(f"Usage: `{command} @user` or `{command} user_id`")
            return

        user_id_match = DIGIT_ID_RE.search(parts[1])
        if not user_id_match:
            await message.channel.send("Could not find a user ID. Mention a user or provide their ID.")
            return

        target_user_id = int(user_id_match.group(1))
        target_user = await resolve_user_from_token(parts[1], message.guild)
        target_label = target_user.mention if target_user else f"`{target_user_id}`"
        admin_ids = set(load_admin_user_ids())

        if command == "!permadd":
            if target_user_id in admin_ids:
                await message.channel.send(f"{target_label} is already a bot admin.")
                return

            admin_ids.add(target_user_id)
            save_admin_user_ids(admin_ids)
            await message.channel.send(f"Added {target_label} as a bot admin.")
            return

        if target_user_id == PERMISSION_OWNER_USER_ID:
            await message.channel.send("The permission owner cannot be removed.")
            return

        if target_user_id not in admin_ids:
            await message.channel.send(f"{target_label} is not a bot admin.")
            return

        admin_ids.remove(target_user_id)
        save_admin_user_ids(admin_ids)
        await message.channel.send(f"Removed {target_label} from bot admins.")
        return

    if command == "!list":
        if not has_admin_access(message):
            return

        pages = build_missing_vehicle_list_pages()
        for page in pages:
            await message.channel.send(page)
        return

    if command == "!vehicles":
        if not has_admin_access(message):
            return

        vehicles = get_vehicle_map()
        total_vehicle_count, fresh_vehicle_count = get_global_inventory_totals(vehicles)
        await message.channel.send(
            "**Vehicle totals**\n"
            f"Total vehicles: **{format_count(total_vehicle_count)}**\n"
            f"Fresh vehicles: **{format_count(fresh_vehicle_count)}**"
        )
        return

    if command == "!check":
        if not has_admin_access(message):
            return

        if len(parts) != 2 or not parts[1].isdigit():
            await message.channel.send("Usage: `!check <message_id>`")
            return

        checked_message_id = int(parts[1])
        vehicle_name = await resolve_spawn_message_vehicle_name(message, checked_message_id)
        if vehicle_name:
            await message.channel.send(vehicle_name)
        else:
            await message.channel.send("I could not find a saved spawn for that message ID.")
        return

    if command in {"!catalogdebug", "!vehicledebug"}:
        if not has_admin_access(message):
            return

        vehicle_query = " ".join(parts[1:]).strip()
        if not vehicle_query:
            await message.channel.send(f"Usage: `{command} vehicle_name`")
            return

        await message.channel.send(build_catalog_debug_message(vehicle_query))
        return

    if command in {"!reloadindex", "!refreshvehicles"}:
        if not has_admin_access(message):
            return

        vehicles = refresh_vehicles()
        log_catalog_audit(vehicles)
        await message.channel.send(f"Reloaded catalog: **{len(vehicles)}** vehicles.")
        return

    if command == "!testspawn":
        if not has_admin_access(message):
            return

        if not message.guild:
            await message.channel.send("This command can only be used in a server.")
            return

        forced_fresh = None
        forced_rarity = None
        testspawn_usage = (
            "Usage: `!testspawn`, `!testspawn true|false`, "
            "or `!testspawn rarity [true|false]`\n"
            "Rarities: art, special, le, exotic, legendary, epic, rare, common"
        )
        testspawn_args = [part.lower() for part in parts[1:]]
        if len(testspawn_args) > 2:
            await message.channel.send(testspawn_usage)
            return

        for testspawn_arg in testspawn_args:
            parsed_fresh = parse_bool_true_false(testspawn_arg)
            if parsed_fresh is not None:
                if forced_fresh is not None:
                    await message.channel.send(testspawn_usage)
                    return
                forced_fresh = parsed_fresh
                continue

            parsed_rarity = parse_testspawn_rarity(testspawn_arg)
            if parsed_rarity:
                if forced_rarity is not None:
                    await message.channel.send(testspawn_usage)
                    return
                forced_rarity = parsed_rarity
                continue

            await message.channel.send(testspawn_usage)
            return

        rarity_weights = {forced_rarity: 1} if forced_rarity else None
        vehicles = get_vehicle_map()
        spawned = await spawn_vehicle(
            vehicles,
            message.channel,
            guild=message.guild,
            force_is_fresh=forced_fresh,
            rarity_weights=rarity_weights,
        )
        if spawned:
            details = []
            if forced_rarity:
                details.append(f"rarity: {display_rarity_name(forced_rarity)}")
            if forced_fresh is not None:
                details.append(f"fresh forced: {'true' if forced_fresh else 'false'}")
            if details:
                await message.channel.send(
                    f"Test spawn sent successfully ({', '.join(details)})."
                )
            else:
                await message.channel.send("Test spawn sent successfully.")
        else:
            if forced_rarity:
                await message.channel.send(
                    f"{display_rarity_name(forced_rarity)} test spawn failed. "
                    "Check vehicle data, images, and spawnable settings for that rarity."
                )
                return
            await message.channel.send("Test spawn failed. Check channel permissions and vehicle data.")
        return

    if command == "!event":
        if not has_admin_access(message):
            return

        if not message.guild:
            await message.channel.send("This command can only be used in a server.")
            return

        event_count_token = ""
        if len(parts) == 2:
            event_count_token = parts[1]
        elif len(parts) == 3 and parts[1].lower() == "count":
            event_count_token = parts[2]
        else:
            await message.channel.send(
                f"Usage: `!event <count>` or `!event count <count>` (max `{EVENT_MAX_SPAWNS}`)"
            )
            return

        event_count = parse_count(event_count_token)
        if event_count is None or event_count <= 0:
            await message.channel.send("Invalid count. Use a positive number (for example: `1`, `10`, `25`).")
            return

        if event_count > EVENT_MAX_SPAWNS:
            await message.channel.send(
                f"Too many event spawns requested. The current limit is `{EVENT_MAX_SPAWNS}` per command."
            )
            return

        vehicles = get_vehicle_map()
        spawned_count = await spawn_event_wave(vehicles, message.channel, guild=message.guild, count=event_count)
        if spawned_count <= 0:
            await message.channel.send("Event spawn failed. Check channel permissions and vehicle data.")
            return
        return

    if command == "!addmoney":
        if not has_admin_access(message):
            return

        if not message.guild:
            await message.channel.send("This command can only be used in a server.")
            return

        if len(parts) < 3:
            await message.channel.send("Usage: `!addmoney @user amount`")
            return

        target_user = await resolve_user_from_token(parts[1], message.guild)
        if target_user is None:
            await message.channel.send("Could not resolve the target user. Mention a user or provide a user ID.")
            return

        amount = parse_count(parts[2])
        if amount is None or amount <= 0:
            await message.channel.send("Invalid amount. Use a positive number (for example: `100`, `1k`, `50k`).")
            return

        new_balance = add_money(target_user.id, amount)
        await message.channel.send(
            f"Added **{format_money(amount)}** to {target_user.mention}. "
            f"New balance: **{format_money(new_balance)}**."
        )
        return

    if command in {"!addinventory", "!removeinventory"}:
        if not has_admin_access(message):
            return

        if not message.guild:
            await message.channel.send("This command can only be used in a server.")
            return

        if len(parts) < 4:
            await message.channel.send(
                "Usage: `!addinventory @user vehicle_name count true|false`\n"
                "Usage: `!removeinventory @user vehicle_name count true|false`"
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
                "Usage: `!addinventory @user vehicle_name count true|false`\n"
                "Usage: `!removeinventory @user vehicle_name count true|false`"
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

    if command == "!sync":
        if message.author.id != PERMISSION_OWNER_USER_ID:
            return

        try:
            synced = await sync_all_commands()
            scope = "Guild-only" if COMMAND_SYNC_MODE == "guild" else "Global"

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

    vehicles = get_vehicle_map()
    print(f"Using data directory: {os.path.abspath(DATA_DIR)}")
    print(f"Vehicle catalog source: {os.path.abspath(VEHICLES_CACHE_PATH) if VEHICLES_CACHE_PATH else 'missing'}")
    print(f"Loaded {len(vehicles)} vehicles from index.json")
    log_catalog_audit(vehicles)
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
    vehicles = get_vehicle_map()
    print(f"Using data directory: {os.path.abspath(DATA_DIR)}")
    print(f"Vehicle catalog source: {os.path.abspath(VEHICLES_CACHE_PATH) if VEHICLES_CACHE_PATH else 'missing'}")
    print(f"Loaded {len(vehicles)} vehicles from index.json")
    log_catalog_audit(vehicles)

    start_website_server()

    if not TOKEN:
        print("No DISCORD_TOKEN found. Set it in environment variables or .env.")
        raise SystemExit(1)

    if ENABLE_INSTANCE_LOCK:
        if not acquire_instance_lock():
            print("Instance lock failed and ENABLE_INSTANCE_LOCK is enabled. Exiting.")
            raise SystemExit(1)
    else:
        print("Instance lock is disabled (ENABLE_INSTANCE_LOCK=false).")

    if AUTO_RESTART_BOT:
        print("Bot auto-restart is enabled.")
    else:
        print("Bot auto-restart is disabled.")

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

        if not AUTO_RESTART_BOT:
            print("Auto-restart is disabled, so the bot process will now exit.")
            raise SystemExit(1)

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, max_retry_delay)
