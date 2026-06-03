# Military Tycoon Vehicle Dex Bot

Military Tycoon Vehicle Dex Bot is a Discord bot for Roblox Military Tycoon communities.

It handles vehicle spawns, catches, inventories, fresh vehicles, coins, trading, market listings, leaderboards, practice games, and server application panels.

## Features

- Automatic vehicle spawns in configured server channels
- Normal, fresh, event, special, and artwork rarity handling
- Inventory pages with vehicle counts, fresh counts, and coin balance
- Coin rewards for catches
- Player trades with vehicles and coins
- Player market and instant base-price selling
- Vehicle and money leaderboards
- Vehicle guessing practice game
- Server settings for spawn channels and wrong-name comments
- Admin application panel dashboard with Discord login
- Per-server application panels, questions, logs, tickets, and accepted-role rewards

## Main Commands

| Command | Description |
| --- | --- |
| `/help` | Show the bot command list |
| `/about` | Show bot information and public links |
| `/show vehicle_name` | Show a vehicle image, rarity, and global counts |
| `/inventory [user]` | Show inventory, fresh totals, and coin balance |
| `/leaderboard` | Switch between vehicle and money leaderboards |
| `/shop buy` | Search and buy vehicles listed by other users |
| `/shop sell sell_type:market vehicle amount price` | List vehicles on the player market |
| `/shop sell sell_type:shop vehicle amount` | Sell vehicles instantly for the base price |
| `/trade @user` | Start a trade request |
| `/tradeadd item amount` | Add vehicles or coins to an active trade |
| `/traderemove item amount` | Remove vehicles or coins from an active trade |

## Server Admin Commands

| Command | Description |
| --- | --- |
| `/dexchannel #channel` | Set the channel used for vehicle spawns |
| `/botcomment public:true/false` | Choose whether wrong-name comments are public or private |

Application panels can be managed from the web dashboard by users who own the server or have Administrator/Manage Server permission.

## Data And Privacy

Runtime inventories, balances, market listings, spawn records, server settings, and application panel data are stored so the bot can provide its features.

See [Terms of Service](TERMS.md) and [Privacy Policy](PRIVACY.md) for public Discord application links.

## Support

Support server: https://discord.gg/yWJHqqBRSJ

This project is not affiliated with Roblox, Discord, or the creators of Military Tycoon.
