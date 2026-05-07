# Dex Bot Final

Dex Bot Final is a Discord vehicle-collection bot. It spawns MT vehicles in a configured Discord channel, lets users catch them, stores inventories, and supports trading and admin tools.

## What It Can Do

- Spawn random vehicles after server activity reaches the configured message threshold.
- Let users catch vehicles with Discord buttons before the spawn expires.
- Track normal and Fresh vehicle counts per user.
- Show vehicle details, rarity, image, and global caught counts with `/show`.
- Show a user's inventory with `/inventory`.
- Show top collectors with `/leaderboard`.
- Let users trade vehicles with `/trade`, `/tradeaccept`, `/tradeadd`, and `/traderemove`.
- Let server admins choose the spawn channel with `/dexchannel`.
- Let bot admins test spawns, run events, reload the vehicle catalog, and manually add or remove inventory.
- Expose a small health endpoint for hosting platforms such as Render.

## Run Locally

1. Install Python 3.11 or newer.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:

   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   ```

4. Start the bot:

   ```bash
   python start.py
   ```

The bot needs the Discord `Message Content Intent` enabled in the Discord Developer Portal, because it counts server messages and handles admin `!` commands.

## Main Settings

- `DISCORD_TOKEN`: required Discord bot token.
- `SPAWN_RATE` or `SPAWN_THRESHOLD`: messages needed before a vehicle spawn. Default: `100`.
- `DATA_DIR`: where inventories, admin IDs, channel settings, and the active `index.json` are stored. Default: local `data`, or `/var/data` on Render.
- `COMMAND_SYNC_MODE`: `global` or `guild`. Default: `global`.
- `COMMAND_SYNC_GUILD_ID`: required only when `COMMAND_SYNC_MODE=guild`.
- `SYNC_INDEX_FROM_REPO`: copy `data/index.json` into `DATA_DIR` on startup. Default: `1`.
- `ENABLE_INSTANCE_LOCK`: prevent running multiple local instances. Default: enabled locally, disabled on Render.
- `AUTO_RESTART_BOT`: retry after startup/network errors. Default: enabled locally, disabled on Render.

## Deploy On Render

This repository includes `render.yaml`. On Render, set `DISCORD_TOKEN` as a secret environment variable. The service starts with:

```bash
python start.py
```

Persistent bot data should use `DATA_DIR=/var/data`, as configured in `render.yaml`.
