from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import discord

import bot as dexbot
import guess_game_patch

guess_game_patch.install(dexbot)


def _health_payload() -> dict[str, object]:
    try:
        vehicles = dexbot.get_vehicle_map()
    except Exception:
        vehicles = {}

    total_vehicle_count = 0
    fresh_vehicle_count = 0
    try:
        inventories = dexbot.load_inventories()
    except Exception:
        inventories = {}

    fresh_suffix = getattr(dexbot, "FRESH_INVENTORY_SUFFIX", "|fresh")
    for user_inventory in inventories.values():
        if not isinstance(user_inventory, dict):
            continue
        for vehicle_key, raw_count in user_inventory.items():
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                continue
            if count <= 0:
                continue
            total_vehicle_count += count
            if str(vehicle_key).endswith(fresh_suffix):
                fresh_vehicle_count += count

    try:
        ready = bool(dexbot.bot.is_ready())
    except Exception:
        ready = False

    online = bool(getattr(dexbot, "BOT_ONLINE", False) and ready)
    bot_user = getattr(dexbot.bot, "user", None)
    started_at = int(getattr(dexbot, "BOT_STARTED_AT", int(time.time())))

    return {
        "running": True,
        "online": online,
        "status": "Bot online" if online else "Bot starting",
        "guild_count": len(getattr(dexbot.bot, "guilds", [])),
        "vehicle_count": len(vehicles),
        "catalog_vehicle_count": len(vehicles),
        "total_vehicle_count": total_vehicle_count,
        "fresh_vehicle_count": fresh_vehicle_count,
        "bot_user": str(bot_user) if bot_user else "Military Tycoon Dex",
        "started_at": started_at,
        "uptime_seconds": max(0, int(time.time()) - started_at),
        "time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path not in {"/", "/health", "/status", "/api/status"}:
            self.send_response(404)
            self.end_headers()
            return

        payload = json.dumps(_health_payload()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_health_server() -> None:
    port_value = os.getenv("PORT")
    if not port_value:
        return

    try:
        port = int(port_value)
    except ValueError:
        print(f"Invalid PORT value {port_value!r}; health server disabled.", flush=True)
        return

    def serve() -> None:
        try:
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
        except OSError as error:
            print(f"Health server failed to bind on port {port}: {error}", flush=True)
            return

        print(f"Health server listening on port {port}", flush=True)
        server.serve_forever()

    Thread(target=serve, name="dexbot-health", daemon=True).start()


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
    start_health_server()
    print_startup_catalog()
    run_bot_forever()


if __name__ == "__main__":
    main()
