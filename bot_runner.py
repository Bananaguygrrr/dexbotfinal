from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

import discord

import bot as dexbot
import guess_game_patch

guess_game_patch.install(dexbot)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


def _safe_vehicle_count() -> int:
    try:
        return len(dexbot.get_vehicle_map())
    except Exception:
        return 0


def _safe_guild_count() -> int:
    try:
        return len(dexbot.bot.guilds)
    except Exception:
        return 0


def _health_payload() -> dict[str, Any]:
    try:
        ready = bool(dexbot.bot.is_ready())
    except Exception:
        ready = False

    online = bool(getattr(dexbot, "BOT_ONLINE", False) and ready)
    bot_user = getattr(dexbot.bot, "user", None)

    return {
        "running": True,
        "online": online,
        "status": "Bot online" if online else "Bot starting or offline",
        "guild_count": _safe_guild_count() if ready else 0,
        "vehicle_count": _safe_vehicle_count(),
        "bot_user": str(bot_user) if bot_user else "",
        "started_at": int(getattr(dexbot, "BOT_STARTED_AT", int(time.time()))),
        "uptime_seconds": max(0, int(time.time()) - int(getattr(dexbot, "BOT_STARTED_AT", int(time.time())))),
        "time": _utc_now(),
    }


class HealthHandler(BaseHTTPRequestHandler):
    def _send_empty(self, status: int = 204) -> None:
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in {"/health", "/status", "/api/status"}:
            self._send_json(_health_payload())
            return
        self._send_empty()

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server() -> None:
    port_value = os.getenv("PORT")
    if not port_value:
        print("No PORT set; health endpoint disabled.", flush=True)
        return

    try:
        port = int(port_value)
    except ValueError:
        print(f"Invalid PORT value: {port_value}", flush=True)
        return

    def _serve() -> None:
        try:
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            print(f"Health endpoint listening on port {port}", flush=True)
            server.serve_forever()
        except Exception as error:
            print(f"Health endpoint error: {error}", flush=True)

    Thread(target=_serve, daemon=True).start()


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
    start_health_server()
    run_bot_forever()


if __name__ == "__main__":
    main()
