# Military Tycoon Vehicle Dex Bot

A Discord vehicle dex and inventory bot for Roblox Military Tycoon communities.

The bot spawns vehicles in configured Discord channels, lets users catch them by name, tracks normal and fresh inventory counts, supports trading, coins, market listings, leaderboards, and a vehicle guessing practice game.

## Features

- Automatic vehicle spawns based on server message activity
- Normal, fresh, event, and special vehicle handling
- Vehicle inventory pages grouped by rarity
- Coin rewards for catches
- Player-to-player trades with vehicles and coins
- Market listings and instant base-price selling
- Vehicle and money leaderboards
- Admin tools for catalog checks, inventory fixes, money fixes, and test spawns
- Server-level settings for spawn channels and wrong-name comment visibility
- Public status website and health endpoint

## Main User Commands

| Command | Description |
| --- | --- |
| `/help` | Show the bot command list |
| `/show vehicle_name` | Show a vehicle image, rarity, and global counts |
| `/inventory [user]` | Show inventory, fresh totals, and coin balance |
| `/leaderboard` | Switch between vehicle and money leaderboards |
| `/shop buy` | Search and buy vehicles listed by other users |
| `/shop sell sell_type:market vehicle amount price` | List vehicles on the player market |
| `/shop sell sell_type:shop (base price) vehicle amount` | Sell vehicles instantly for the configured base price |
| `/trade @user` | Start a trade request |
| `/tradeadd item amount` | Add vehicles or coins to an active trade |
| `/traderemove item amount` | Remove vehicles or coins from an active trade |

## Server Admin Commands

| Command | Description |
| --- | --- |
| `/dexchannel #channel` | Set the channel used for vehicle spawns |
| `/botcomment public:true/false` | Choose whether wrong-name comments are public or private |

## Bot Admin Commands

| Command | Description |
| --- | --- |
| `!list` | List vehicles without picture links |
| `!vehicles` | Show total caught vehicles and fresh vehicles |
| `!check <message_id>` | Show the hidden vehicle name for a spawn message |
| `!testspawn [special] [true/false]` | Spawn a test vehicle |
| `!event <count>` | Spawn an event wave |
| `!addinventory @user vehicle_name count true/false` | Add normal or fresh inventory |
| `!removeinventory @user vehicle_name count true/false` | Remove normal or fresh inventory |
| `!addmoney @user amount` | Add coins to a user |

## Project Layout

```text
.
|-- bot.py               # Main Discord bot, website, catalog, inventory, trading, shop logic
|-- bot_runner.py        # Production runner with health/status endpoint
|-- guess_game_patch.py  # Vehicle guessing practice game command
|-- data/index.json      # Vehicle catalog used by the bot
|-- render.yaml          # Render deployment configuration
|-- .env.example         # Local environment template
|-- TERMS.md             # Terms of Service
|-- PRIVACY.md           # Privacy Policy
|-- SUPPORT.md           # Support information
`-- SECURITY.md          # Security reporting information
```

## Configuration

Copy `.env.example` to `.env` for local development and fill in your values.

The important production variables are:

| Variable | Purpose |
| --- | --- |
| `DISCORD_TOKEN` | Discord bot token |
| `DATA_DIR` | Persistent data directory, usually `/var/data` on Render |
| `SPAWN_RATE` | Guild messages required before a normal spawn |
| `SPAWN_DESPAWN_SECONDS` | Normal spawn timeout |
| `FRESH_SPAWN_CHANCE` | Normal fresh spawn chance |
| `EVENT_FRESH_SPAWN_CHANCE` | Event fresh spawn chance |
| `EVENT_SPAWN_DESPAWN_SECONDS` | Event spawn timeout |
| `SELL_VEHICLE_PRICE` | Instant shop sell price per vehicle |
| `COMMAND_SYNC_MODE` | Slash command sync mode, usually `global` |

## Local Checks

Run the same lightweight compile check used during deploy:

```bash
python -m py_compile bot.py bot_runner.py guess_game_patch.py
```

Render uses the same compile check, then starts the bot with `python3 bot_runner.py`.

## Data And Privacy

Runtime inventories, balances, market listings, spawn records, and server settings are stored in the configured data directory. These runtime files should not be committed to Git.

See [Terms of Service](TERMS.md) and [Privacy Policy](PRIVACY.md) for public Discord application links.

## Support

Support server: https://discord.gg/yWJHqqBRSJ

This project is not affiliated with Roblox, Discord, or the creators of Military Tycoon.
