from __future__ import annotations

import os
import time

import discord

import bot as dexbot
import guess_game_patch

guess_game_patch.install(dexbot)


def print_startup_catalog() -> None:
    vehicles = dexbot.get_vehicle_map()
    print(f"Using data directory: {os.path.abspath(dexbot.DATA_DIR)}", flush=True)
    print(
        "Vehicle catalog source: "
        f"{os.path.abspath(dexbot.VEHICLES_CACHE_PATH) if dexbot.VEHICLES_CACHE_PATH else 'missing'}",
        flush=True,
    )
    print(f"Loaded {len(vehicles)} vehicles from index.json", flush=True)
    dexbot.log_catalog_audit(vehicles)


def run_bot_forever() -> None:
    if not dexbot.TOKEN:
        print("No DISCORD_TOKEN found. Set it in environment variables or .env.", flush=True)
        raise SystemExit(1)

    if dexbot.ENABLE_INSTANCE_LOCK:
        if not dexbot.acquire_instance_lock():
            print("Instance lock failed and ENABLE_INSTANCE_LOCK is enabled. Exiting.", flush=True)
            raise SystemExit(1)
    else:
        print("Instance lock is disabled (ENABLE_INSTANCE_LOCK=false).", flush=True)

    if dexbot.AUTO_RESTART_BOT:
        print("Bot auto-restart is enabled.", flush=True)
    else:
        print("Bot auto-restart is disabled.", flush=True)

    retry_delay = 15
    max_retry_delay = 3600

    while True:
        try:
            dexbot.bot.run(dexbot.TOKEN)
            break
        except discord.LoginFailure as error:
            print(f"Discord login failed (token issue): {error}", flush=True)
            break
        except discord.HTTPException as error:
            error_text = str(error)
            if "1015" in error_text or "You are being rate limited" in error_text:
                retry_delay = max(retry_delay, 900)
                print(f"Cloudflare/Discord rate-limit block detected. Retrying in {retry_delay}s...", flush=True)
            else:
                print(f"Discord HTTP error on startup: {error}. Retrying in {retry_delay}s...", flush=True)
        except Exception as error:
            print(f"Unexpected bot startup error: {error}. Retrying in {retry_delay}s...", flush=True)

        if not dexbot.AUTO_RESTART_BOT:
            print("Auto-restart is disabled, so the bot process will now exit.", flush=True)
            raise SystemExit(1)

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, max_retry_delay)


def main() -> None:
    print_startup_catalog()
    run_bot_forever()


if __name__ == "__main__":
    main()
