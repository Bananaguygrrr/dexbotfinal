from __future__ import annotations

import builtins
import html
import json
import os
import shutil
import sys
import time
from typing import Any
from urllib.parse import urlparse


_ORIGINAL_IMPORT = builtins.__import__
_PATCHED_BOT_MODULE_IDS: set[int] = set()
_INVENTORY_BACKUP_DONE = False


def _truthy_env(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _display_vehicle_name(dexbot: Any, vehicle_name: str) -> str:
    try:
        label = dexbot.display_vehicle_name(vehicle_name)
    except Exception:
        label = str(vehicle_name or "")
    return str(label or vehicle_name).replace("_", " ")


def _display_rarity_name(dexbot: Any, rarity: str) -> str:
    try:
        return dexbot.display_rarity_name(rarity)
    except Exception:
        return str(rarity or "common").title()


def _vehicle_image_url(dexbot: Any, vehicle_data: dict[str, Any]) -> str:
    for key in ("url", "pic_link", "image"):
        value = str(vehicle_data.get(key) or "").strip()
        if value:
            try:
                if dexbot.is_http_url(value):
                    return value
            except Exception:
                parsed = urlparse(value)
                if parsed.scheme in {"http", "https"}:
                    return value
    return ""


def _vehicle_catalog_items(dexbot: Any) -> list[dict[str, str]]:
    vehicles = dexbot.get_vehicle_map()
    rarity_order = {
        str(rarity).lower(): index
        for index, rarity in enumerate(getattr(dexbot, "RARITY_ORDER", ()))
    }

    items: list[dict[str, str]] = []
    for vehicle_name, vehicle_data in vehicles.items():
        if not isinstance(vehicle_data, dict):
            continue

        rarity = str(vehicle_data.get("rarity") or "common").strip().lower()
        image_url = _vehicle_image_url(dexbot, vehicle_data)
        items.append(
            {
                "name": str(vehicle_name),
                "display_name": _display_vehicle_name(dexbot, str(vehicle_name)),
                "rarity": rarity,
                "rarity_label": _display_rarity_name(dexbot, rarity),
                "image_url": image_url,
            }
        )

    items.sort(
        key=lambda item: (
            rarity_order.get(item["rarity"], 999),
            item["display_name"].lower(),
        )
    )
    return items


def _render_vehicle_page(dexbot: Any) -> bytes:
    items = _vehicle_catalog_items(dexbot)
    rarity_counts: dict[str, int] = {}
    for item in items:
        rarity_counts[item["rarity_label"]] = rarity_counts.get(item["rarity_label"], 0) + 1

    filters = ["All"] + sorted(rarity_counts)
    filter_buttons = "\n".join(
        f'<button class="filter{" active" if rarity == "All" else ""}" data-rarity="{html.escape(rarity)}">'
        f'{html.escape(rarity)}'
        "</button>"
        for rarity in filters
    )

    cards = []
    for item in items:
        color = getattr(dexbot, "RARITY_COLORS", {}).get(item["rarity"], 0x808080)
        image_url = html.escape(item["image_url"], quote=True)
        image_html = (
            f'<img src="{image_url}" alt="{html.escape(item["display_name"], quote=True)}" loading="lazy">'
            if image_url
            else '<div class="missing-image">No image</div>'
        )
        cards.append(
            '<article class="vehicle" '
            f'data-name="{html.escape((item["display_name"] + " " + item["name"]).lower(), quote=True)}" '
            f'data-rarity="{html.escape(item["rarity_label"], quote=True)}">'
            f'<div class="image-wrap">{image_html}</div>'
            '<div class="vehicle-info">'
            f'<h2>{html.escape(item["display_name"])}</h2>'
            f'<span class="rarity" style="--rarity-color: #{color:06x}">{html.escape(item["rarity_label"])}</span>'
            f'<code>{html.escape(item["name"])}</code>'
            '</div>'
            '</article>'
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Military Tycoon Dex Vehicles</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #101114;
      --panel: #1b1d22;
      --panel-2: #23262d;
      --text: #f4f5f7;
      --muted: #aeb4c0;
      --line: #333842;
      --accent: #38d08f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 10;
      background: rgba(16, 17, 20, 0.96);
      border-bottom: 1px solid var(--line);
      padding: 18px clamp(16px, 4vw, 42px);
    }}
    .topline {{
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(24px, 3vw, 40px);
      font-weight: 800;
    }}
    .count {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
    }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(180px, 360px) 1fr;
      gap: 12px;
      align-items: center;
    }}
    input {{
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      color: var(--text);
      padding: 0 13px;
      font: inherit;
      outline: none;
    }}
    input:focus {{ border-color: var(--accent); }}
    .filters {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 2px;
    }}
    .filter {{
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      color: var(--text);
      padding: 0 12px;
      font-weight: 700;
      cursor: pointer;
      white-space: nowrap;
    }}
    .filter.active {{
      background: var(--accent);
      color: #06110c;
      border-color: var(--accent);
    }}
    main {{
      padding: 22px clamp(16px, 4vw, 42px) 44px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
      gap: 14px;
    }}
    .vehicle {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      min-width: 0;
    }}
    .image-wrap {{
      aspect-ratio: 16 / 10;
      display: grid;
      place-items: center;
      background: var(--panel-2);
      border-bottom: 1px solid var(--line);
    }}
    img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
      padding: 10px;
    }}
    .missing-image {{
      color: var(--muted);
      font-weight: 800;
      font-size: 14px;
    }}
    .vehicle-info {{
      padding: 12px;
      display: grid;
      gap: 8px;
    }}
    h2 {{
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .rarity {{
      width: fit-content;
      border-left: 4px solid var(--rarity-color);
      background: #111318;
      color: var(--text);
      padding: 5px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 800;
    }}
    code {{
      color: var(--muted);
      overflow-wrap: anywhere;
      font-size: 12px;
    }}
    .hidden {{ display: none; }}
    @media (max-width: 720px) {{
      .controls {{ grid-template-columns: 1fr; }}
      .grid {{ grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topline">
      <h1>Military Tycoon Dex Vehicles</h1>
      <div class="count"><span id="visible-count">{len(items)}</span> / {len(items)} vehicles</div>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Search vehicles" autocomplete="off">
      <div class="filters">{filter_buttons}</div>
    </div>
  </header>
  <main>
    <section class="grid" id="vehicle-grid">
      {''.join(cards)}
    </section>
  </main>
  <script>
    const search = document.querySelector('#search');
    const filters = [...document.querySelectorAll('.filter')];
    const cards = [...document.querySelectorAll('.vehicle')];
    const visibleCount = document.querySelector('#visible-count');
    let activeRarity = 'All';

    function applyFilters() {{
      const query = search.value.trim().toLowerCase();
      let shown = 0;
      for (const card of cards) {{
        const matchesText = !query || card.dataset.name.includes(query);
        const matchesRarity = activeRarity === 'All' || card.dataset.rarity === activeRarity;
        const visible = matchesText && matchesRarity;
        card.classList.toggle('hidden', !visible);
        if (visible) shown += 1;
      }}
      visibleCount.textContent = shown;
    }}

    search.addEventListener('input', applyFilters);
    filters.forEach(button => {{
      button.addEventListener('click', () => {{
        activeRarity = button.dataset.rarity;
        filters.forEach(item => item.classList.toggle('active', item === button));
        applyFilters();
      }});
    }});
  </script>
</body>
</html>
"""
    return page.encode("utf-8")


def _catalog_json_bytes(dexbot: Any) -> bytes:
    return json.dumps(_vehicle_catalog_items(dexbot), ensure_ascii=True, indent=2).encode("utf-8")


def _install_catalog_website(dexbot: Any) -> None:
    base_handler = getattr(dexbot, "BaseHTTPRequestHandler", None)
    if base_handler is None:
        from http.server import BaseHTTPRequestHandler as base_handler

    class VehicleCatalogHealthHandler(base_handler):  # type: ignore[misc, valid-type]
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path in {"/", "/vehicles"}:
                self._send_bytes(_render_vehicle_page(dexbot), "text/html; charset=utf-8")
                return
            if path == "/api/vehicles":
                self._send_bytes(_catalog_json_bytes(dexbot), "application/json; charset=utf-8")
                return
            if path in {"/health", "/status"}:
                payload = {
                    "running": True,
                    "online": bool(getattr(dexbot, "BOT_ONLINE", False)),
                    "vehicles": len(dexbot.get_vehicle_map()),
                    "catalog": os.path.abspath(getattr(dexbot, "VEHICLES_CACHE_PATH", "") or ""),
                }
                self._send_bytes(json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")
                return
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")

        def _send_bytes(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    dexbot._HealthHandler = VehicleCatalogHealthHandler


def _backup_inventory_file(dexbot: Any, reason: str) -> str:
    global _INVENTORY_BACKUP_DONE
    if _INVENTORY_BACKUP_DONE:
        return ""

    inventory_path = getattr(dexbot, "USER_INVENTORIES_FILE", "")
    if not inventory_path or not os.path.exists(inventory_path):
        _INVENTORY_BACKUP_DONE = True
        return ""

    backup_dir = os.path.join(os.path.dirname(inventory_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(backup_dir, f"user_inventories-{stamp}-{reason}.json")
    shutil.copy2(inventory_path, backup_path)
    _INVENTORY_BACKUP_DONE = True
    print(f"Backed up user inventories before catalog migration: {backup_path}")
    return backup_path


def _install_inventory_backup(dexbot: Any) -> None:
    original_save = dexbot.save_inventories
    original_prune = dexbot.prune_inventories_to_vehicle_names

    def save_inventories_with_backup(inventories: dict[str, dict[str, int]]) -> None:
        try:
            _backup_inventory_file(dexbot, "before-save")
        except Exception as error:
            print(f"Inventory backup failed before save: {error}")
        original_save(inventories)

    def prune_inventories_with_backup(vehicle_names: set[str]) -> None:
        try:
            _backup_inventory_file(dexbot, "before-catalog-migration")
        except Exception as error:
            print(f"Inventory backup failed before catalog migration: {error}")
        original_prune(vehicle_names)

    dexbot.save_inventories = save_inventories_with_backup
    dexbot.prune_inventories_to_vehicle_names = prune_inventories_with_backup


def _patch_bot_module(dexbot: Any) -> None:
    module_id = id(dexbot)
    if module_id in _PATCHED_BOT_MODULE_IDS:
        return

    required_attrs = (
        "save_inventories",
        "prune_inventories_to_vehicle_names",
        "get_vehicle_map",
        "BaseHTTPRequestHandler",
    )
    if any(not hasattr(dexbot, attr) for attr in required_attrs):
        return

    _PATCHED_BOT_MODULE_IDS.add(module_id)

    _install_inventory_backup(dexbot)
    _install_catalog_website(dexbot)

    if _truthy_env("SUPPRESS_CATALOG_AUDIT", "1"):
        dexbot.log_catalog_audit = lambda vehicles: None

    builtins.__import__ = _ORIGINAL_IMPORT
    print("Runtime patch installed: vehicle website, safe inventory catalog migration, audit logs suppressed.")


def _import_with_bot_patch(name: str, globals: Any = None, locals: Any = None, fromlist: Any = (), level: int = 0) -> Any:
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if level == 0 and name.split(".", 1)[0] == "bot":
        dexbot = sys.modules.get("bot")
        if dexbot is not None:
            _patch_bot_module(dexbot)
    return module


builtins.__import__ = _import_with_bot_patch
