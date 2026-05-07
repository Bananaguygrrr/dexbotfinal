from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path("/var/data") if os.getenv("RENDER") and not os.getenv("DATA_DIR") else SCRIPT_DIR / "data"
DATA_DIR = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
ROOT_INDEX_JSON_FILE = SCRIPT_DIR / "data" / "index.json"
PERSISTENT_INDEX_JSON_FILE = DATA_DIR / "index.json"

REMOVED_RARITIES = {"uncommon"}
VALID_RARITIES = {
    "specials",
    "limited edition",
    "exotic",
    "legendary",
    "epic",
    "rare",
    "common",
}
SYNC_INDEX_FROM_REPO = os.getenv("SYNC_INDEX_FROM_REPO", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def normalize_catalog_rarity(raw_rarity: Any) -> str:
    rarity = str(raw_rarity or "common").strip().lower()
    if rarity in REMOVED_RARITIES:
        return "common"
    return rarity if rarity in VALID_RARITIES else "common"


def ensure_data_dir() -> None:
    global DATA_DIR, PERSISTENT_INDEX_JSON_FILE

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        fallback_data_dir = SCRIPT_DIR / "data"
        print(f"Failed to access DATA_DIR '{DATA_DIR}': {error}. Falling back to '{fallback_data_dir}'.")
        DATA_DIR = fallback_data_dir
        PERSISTENT_INDEX_JSON_FILE = DATA_DIR / "index.json"
        DATA_DIR.mkdir(parents=True, exist_ok=True)


def sync_index_from_repo() -> None:
    if not SYNC_INDEX_FROM_REPO:
        print("SYNC_INDEX_FROM_REPO is disabled; keeping existing index.json.")
        return

    if not ROOT_INDEX_JSON_FILE.exists():
        print(f"No repo index found at {ROOT_INDEX_JSON_FILE}; keeping existing index.json.")
        return

    with ROOT_INDEX_JSON_FILE.open("r", encoding="utf-8-sig") as handle:
        catalog = json.load(handle)

    if not isinstance(catalog, dict):
        raise ValueError("data/index.json must be a top-level JSON object.")

    for vehicle_name, vehicle_data in catalog.items():
        if not isinstance(vehicle_data, dict):
            raise ValueError(f"data/index.json entry {vehicle_name!r} must be an object.")
        vehicle_data["rarity"] = normalize_catalog_rarity(vehicle_data.get("rarity"))

    ensure_data_dir()
    tmp_path = PERSISTENT_INDEX_JSON_FILE.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(catalog, handle, indent=4)
        handle.write("\n")

    os.replace(tmp_path, PERSISTENT_INDEX_JSON_FILE)
    print(f"Synced repo data/index.json to {PERSISTENT_INDEX_JSON_FILE}: {len(catalog)} vehicles.")


def remove_runtime_rarities(bot_module: ModuleType) -> None:
    removed = REMOVED_RARITIES

    bot_module.RARITY_ORDER = tuple(
        rarity for rarity in getattr(bot_module, "RARITY_ORDER", ()) if rarity not in removed
    )
    bot_module.RARITY_WEIGHTS = {
        rarity: weight
        for rarity, weight in getattr(bot_module, "RARITY_WEIGHTS", {}).items()
        if rarity not in removed
    }
    bot_module.EVENT_RARITY_WEIGHTS = {
        rarity: weight
        for rarity, weight in getattr(bot_module, "EVENT_RARITY_WEIGHTS", {}).items()
        if rarity not in removed
    }
    for rarity in removed:
        getattr(bot_module, "RARITY_COLORS", {}).pop(rarity, None)


def run_bot() -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    import bot as dexbot

    remove_runtime_rarities(dexbot)

    vehicles = dexbot.get_vehicle_map()
    print(f"Using data directory: {os.path.abspath(dexbot.DATA_DIR)}")
    print(
        "Vehicle catalog source: "
        f"{os.path.abspath(dexbot.VEHICLES_CACHE_PATH) if dexbot.VEHICLES_CACHE_PATH else 'missing'}"
    )
    print(f"Loaded {len(vehicles)} vehicles from index.json")

    dexbot.start_website_server()

    if not dexbot.TOKEN:
        print("No DISCORD_TOKEN found. Set it in environment variables or .env.")
        raise SystemExit(1)

    if dexbot.ENABLE_INSTANCE_LOCK:
        if not dexbot.acquire_instance_lock():
            print("Instance lock failed and ENABLE_INSTANCE_LOCK is enabled. Exiting.")
            raise SystemExit(1)
    else:
        print("Instance lock is disabled (ENABLE_INSTANCE_LOCK=false).")

    if dexbot.AUTO_RESTART_BOT:
        print("Bot auto-restart is enabled.")
    else:
        print("Bot auto-restart is disabled.")

    retry_delay = 15
    max_retry_delay = 3600

    while True:
        try:
            dexbot.bot.run(dexbot.TOKEN)
            break
        except dexbot.discord.LoginFailure as error:
            print(f"Discord login failed (token issue): {error}")
            break
        except dexbot.discord.HTTPException as error:
            error_text = str(error)
            if "1015" in error_text or "You are being rate limited" in error_text:
                retry_delay = max(retry_delay, 900)
                print(f"Cloudflare/Discord rate-limit block detected. Retrying in {retry_delay}s...")
            else:
                print(f"Discord HTTP error on startup: {error}. Retrying in {retry_delay}s...")
        except Exception as error:
            print(f"Unexpected bot startup error: {error}. Retrying in {retry_delay}s...")

        if not dexbot.AUTO_RESTART_BOT:
            print("Auto-restart is disabled, so the bot process will now exit.")
            raise SystemExit(1)

        dexbot.time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, max_retry_delay)


if __name__ == "__main__":
    sync_index_from_repo()
    run_bot()
