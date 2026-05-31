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
- Server-level settings for spawn channels and wrong-name comment visibility
- Public status website and health endpoint

## Main User Commands

| Command | Description |
| --- | --- |
| `/help` | Show the bot command list |
| `/about` | Show bot information, stats, and links |
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

## Project Layout

```text
.
|-- bot.py               # Main Discord bot, website, catalog, inventory, trading, shop logic
|-- bot_runner.py        # Production runner with health/status endpoint
|-- application_system.py # Application panels, questions, DM flow, and review logs
|-- guess_game_patch.py  # Vehicle guessing practice game command
|-- data/index.json      # Vehicle catalog used by the bot
|-- TERMS.md             # Terms of Service
|-- PRIVACY.md           # Privacy Policy
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
| `APPLICATION_STATE_DIR` | Optional custom directory for per-server application panel/question storage |
| `APPLICATION_STATE_FILE` | Optional legacy import path for old combined application storage |
| `APPLICATION_TIMEOUT_SECONDS` | Time users have to finish an application |
| `COMMAND_SYNC_MODE` | Slash command sync mode, usually `global` |

## Local Checks

Run the same lightweight compile check used during deploy:

```bash
python -m py_compile bot.py bot_runner.py guess_game_patch.py application_system.py
```

Render uses the same compile check, then starts the bot with `python3 bot_runner.py`.

## Data And Privacy

Runtime inventories, balances, market listings, spawn records, application panels, application questions, application submissions, and server settings are stored in the configured data directory. These runtime files should not be committed to Git.

Application settings are saved per server inside `DATA_DIR/applications/` by default, for example `applications/123456789012345678.json`. Each server file also gets a `.bak` recovery backup. Old combined `applications.json` data is imported automatically, but new changes are written per server. On Render, keep `DATA_DIR` on the persistent disk, usually `/var/data`, so deploys do not reset server setup.

See [Terms of Service](TERMS.md) and [Privacy Policy](PRIVACY.md) for public Discord application links.

## Support

Support server: https://discord.gg/yWJHqqBRSJ

This project is not affiliated with Roblox, Discord, or the creators of Military Tycoon.
