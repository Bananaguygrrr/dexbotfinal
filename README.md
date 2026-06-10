# Military Tycoon Vehicle Dex Bot

Military Tycoon Vehicle Dex Bot is a Discord bot for Roblox Military Tycoon communities.

It handles vehicle spawns, catches, inventories, fresh vehicles, coins, trading, market listings, leaderboards, practice games, and server application panels.
It also includes server giveaways with button entries, participant lists, manager roles, rerolls, role and message requirements, uploaded images, winner roles, and winner DMs.

## Features

- Automatic vehicle spawns in configured server channels
- Normal, fresh, event, special, and artwork rarity handling
- Inventory pages with vehicle counts, fresh counts, and coin balance
- Coin rewards for catches
- Player trades with vehicles and coins
- Player market and instant base-price selling
- Vehicle and money leaderboards
- Vehicle guessing practice game
- Server giveaways with entry buttons, participant lists, participant removal, rerolls, role requirements, message requirements, extra role entries, winner roles, and uploaded images
- Server settings for spawn channels and wrong-name comments
- Admin application panel dashboard with Discord login
- Per-server application panels, questions, logs, tickets, and accepted-role rewards

## Main Commands

| Command | Description |
| --- | --- |
| `/help` | Show the bot command list |
| `/about` | Show bot information and public links |
| `/show vehicle_name` | Show a vehicle image, rarity, and global counts |
| `/game [rounds]` | Start a vehicle guessing practice game |
| `/inventory [user]` | Show inventory, fresh totals, and coin balance |
| `/leaderboard` | Switch between vehicle and money leaderboards |
| `/shop buy` | Search and buy vehicles listed by other users |
| `/shop sell sell_type:market vehicle amount price` | List vehicles on the player market |
| `/shop sell sell_type:shop vehicle amount` | Sell vehicles instantly for the base price |
| `/trade @user` | Start a trade request |
| `/tradeaccept @user` | Accept a trade request |
| `/tradeadd item amount` | Add vehicles or coins to an active trade |
| `/traderemove item amount` | Remove vehicles or coins from an active trade |

## Server Admin Commands

| Command | Description |
| --- | --- |
| `/dexchannel #channel` | Set the channel used for vehicle spawns |
| `/botcomment public:true/false` | Choose whether wrong-name comments are public or private |
| `/giveaway create duration winners prize` | Create a giveaway with role requirements, message requirements, extra entries, and uploaded images |
| `/giveaway edit giveaway_id` | Edit an active giveaway or clear images, requirements, and extra entries |
| `/giveaway delete giveaway_id` | Delete a giveaway |
| `/giveaway end giveaway_id` | End a giveaway early |
| `/giveaway fix giveaway_id` | Re-render a giveaway if the message view is broken |
| `/giveaway reroll giveaway_id` | Reroll an ended giveaway |
| `/giveaway remove-participant giveaway_id user` | Remove a user from a giveaway |
| `/giveaway creator-roles` | Set roles that can create giveaways |
| `/giveaway manager-roles` | Set roles that can manage giveaways |
| `/application panel #channel` | Post or refresh the application dropdown panel |
| `/application log #channel` | Set the application log and review channel |
| `/application text text` | Update the text shown on the application panel |
| `/application create-panel` | Create an application option |
| `/application edit-panel` | Edit an application option |
| `/application delete-panel` | Delete an application option |
| `/application add-question` | Add a text or dropdown question |
| `/application edit-question` | Edit a question |
| `/application delete-question` | Delete a question and renumber the rest |
| `/application accepted-role` | Set the role given when a panel is accepted |

Application panels can also be managed from the web dashboard by users who own the server or have Administrator/Manage Server permission.

## Data And Privacy

Runtime inventories, balances, market listings, spawn records, server settings, and application panel data are stored so the bot can provide its features.

See [Terms of Service](TERMS.md) and [Privacy Policy](PRIVACY.md) for public Discord application links.

## Support

Support server: https://discord.gg/yWJHqqBRSJ

This project is not affiliated with Roblox, Discord, or the creators of Military Tycoon.
