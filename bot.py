import builtins
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import discord
from discord import app_commands

import app_state
from config import DATA_DIR, SPAWN_THRESHOLD, TOKEN
from inventory_views import InventoryOverview, create_overview_embed
from spawning import rainbow_task, spawn_in_guild, spawn_vehicle
from storage import acquire_instance_lock
from trade_commands import register_trade_commands
from utils import safe_send
from vehicle_data import get_vehicle_map, refresh_vehicles


def print_flush(*args, **kwargs):
    builtins.print(*args, **kwargs)
    sys.stdout.flush()


print = print_flush


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        payload = {
            "running": True,
            "online": bool(app_state.BOT_ONLINE)
        }
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def log_message(self, format, *args):
        return


def start_health_server():
    port_value = os.getenv('PORT')
    if not port_value:
        return
    try:
        port = int(port_value)
    except ValueError:
        print(f"Invalid PORT value: {port_value}")
        return

    def _serve():
        try:
            server = HTTPServer(('0.0.0.0', port), _HealthHandler)
            print(f"Health server listening on port {port}")
            server.serve_forever()
        except Exception as error:
            print(f"Health server error: {error}")

    Thread(target=_serve, daemon=True).start()


async def sync_all_commands():
    synced = await app_state.bot.tree.sync()
    print(f"Globally synced {len(synced)} command(s)")

    for guild in app_state.bot.guilds:
        try:
            app_state.bot.tree.copy_global_to(guild=guild)
            guild_synced = await app_state.bot.tree.sync(guild=guild)
            print(f"Guild synced {len(guild_synced)} command(s) in {guild.name}")
        except Exception as guild_error:
            print(f"Error syncing guild {guild.name}: {guild_error}")

    print(f"Sync complete. Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages.")
    return synced


register_trade_commands(app_state.bot)


@app_state.bot.tree.command(name="show", description="Show a vehicle's picture and rarity")
@app_commands.describe(vehicle_name="The name of the vehicle to show")
async def show_vehicle(interaction: discord.Interaction, vehicle_name: str):
    vehicles = get_vehicle_map()
    if vehicle_name not in vehicles:
        matching_names = [name for name in vehicles if name.lower() == vehicle_name.lower()]
        if matching_names:
            vehicle_name = matching_names[0]
        else:
            await interaction.response.send_message(f"❌ Vehicle **{vehicle_name.replace('-', '')}** not found.", ephemeral=True)
            return

    vehicle_data = vehicles[vehicle_name]
    rarity = vehicle_data.get('rarity', 'Common')
    local_path = vehicle_data.get('local_path')
    image_url = vehicle_data.get('url')

    embed = discord.Embed(
        title=vehicle_name.replace('-', ''),
        color=discord.Color({
            "limited edition": 0x8B0000,
            "exotic": 0xFF00FF,
            "legendary": 0xFFD700,
            "epic": 0x800080,
            "rare": 0x0000FF,
            "common": 0x808080,
        }.get(rarity.lower(), 0x808080))
    )
    embed.add_field(name="Rarity", value=rarity.title(), inline=True)

    if image_url and str(image_url).startswith('http'):
        embed.set_image(url=image_url)
        await interaction.response.send_message(embed=embed)
        return

    if local_path:
        file = discord.File(local_path, filename="vehicle.png")
        embed.set_image(url="attachment://vehicle.png")
        await interaction.response.send_message(embed=embed, file=file)
        return

    embed.description = "This vehicle has no picture yet."
    await interaction.response.send_message(embed=embed)


@show_vehicle.autocomplete('vehicle_name')
async def show_vehicle_autocomplete(interaction: discord.Interaction, current: str):
    vehicles = get_vehicle_map()
    return [
        app_commands.Choice(name=name.replace('-', ''), value=name)
        for name in vehicles
        if current.lower() in name.lower() or current.lower() in name.lower().replace('-', '')
    ][:25]


@app_state.bot.tree.command(name="testspawn", description="Developer command to force a vehicle spawn")
@app_commands.guild_only()
async def testspawn_slash(interaction: discord.Interaction):
    if not interaction.guild or not interaction.channel:
        await safe_send(interaction, "This command can only be used in a server.", ephemeral=True)
        return
    if not interaction.permissions.manage_guild:
        await safe_send(interaction, "You need Manage Server permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    vehicles = refresh_vehicles()
    spawned = await spawn_vehicle(vehicles, interaction.channel, guild=interaction.guild)
    if spawned:
        await interaction.followup.send("Test spawn sent successfully.", ephemeral=True)
    else:
        await interaction.followup.send("Test spawn failed. Check channel permissions and vehicle data.", ephemeral=True)


@app_state.bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"App command error in /{interaction.command.name if interaction.command else 'unknown'}: {error}")
    original_error = getattr(error, "original", error)
    if isinstance(original_error, (discord.NotFound, discord.HTTPException)):
        print("Interaction response failed. If this keeps happening, make sure only one bot instance is running with this token.")


@app_state.bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg_content = message.content.lower()
    if msg_content.startswith('!inv') or msg_content.startswith('!inventory'):
        parts = message.content.split()
        if parts and parts[0].lower() in ['!inv', '!inventory']:
            target_user = message.author
            if message.mentions:
                target_user = message.mentions[0]
            elif len(parts) > 1:
                import re

                user_id_match = re.search(r'(\d+)', parts[1])
                if user_id_match:
                    user_id = int(user_id_match.group(1))
                    try:
                        potential_user = await app_state.bot.fetch_user(user_id)
                        if potential_user:
                            target_user = potential_user
                    except Exception:
                        pass

            await message.channel.send(
                embed=create_overview_embed(target_user),
                view=InventoryOverview(target_user, message.author)
            )
            return

    if message.content.lower() in ['!help', '!h']:
        help_text = (
            "**MT Vehicle Bot Commands:**\n"
            "`/show` - Show a vehicle's picture and rarity\n"
            "`!inventory` or `!inv` - View your caught vehicles\n"
            "`/inventory` - View a vehicle inventory\n"
            "`/trade` - Send a trade request to another user\n"
            "`/tradeaccept` - Accept a trade request\n"
            "`/tradeadd` - Add vehicles to a trade\n"
            "`/traderemove` - Remove vehicles from a trade\n"
            "`/testspawn` - Force a test spawn\n"
            "`!sync` - Manually sync slash commands (if they are missing)\n\n"
            f"*Vehicles spawn automatically every {SPAWN_THRESHOLD} messages!*"
        )
        await message.channel.send(help_text)
        return

    if message.content.lower() == '!sync':
        try:
            if message.guild:
                app_state.bot.tree.copy_global_to(guild=message.guild)
                synced = await app_state.bot.tree.sync(guild=message.guild)
                scope = "Guild"
            else:
                synced = await sync_all_commands()
                scope = "Global"

            synced_names = [f"/{command.name}" for command in synced]
            await message.channel.send(
                f"{scope} synced {len(synced)} slash command(s) successfully!\n"
                f"{', '.join(synced_names)}\n"
                f"Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages."
            )
        except Exception as error:
            await message.channel.send(f"Error syncing slash commands: {error}")
        return

    if message.guild:
        guild_id = message.guild.id
        app_state.guild_msg_counts[guild_id] = app_state.guild_msg_counts.get(guild_id, 0) + 1
        if app_state.guild_msg_counts[guild_id] >= SPAWN_THRESHOLD:
            app_state.guild_msg_counts[guild_id] = 0
            await spawn_in_guild(message.guild)


@app_state.bot.event
async def on_ready():
    app_state.BOT_ONLINE = True
    print(f"Using data directory: {os.path.abspath(DATA_DIR)}")
    print(f"Loaded {len(get_vehicle_map())} vehicles from index.json")
    print(f"Bot is logged in as {app_state.bot.user.name} | pid={os.getpid()} | started={app_state.BOT_STARTED_AT}")
    print(f"Bot ready. Commands are synced. Spawn rate: 1 vehicle every {SPAWN_THRESHOLD} guild messages.")
    if not rainbow_task.is_running():
        rainbow_task.start()


async def setup_hook():
    try:
        await sync_all_commands()
    except Exception as error:
        print(f"Error syncing tree during setup: {error}")


app_state.bot.setup_hook = setup_hook


@app_state.bot.event
async def on_disconnect():
    app_state.BOT_ONLINE = False


if __name__ == '__main__':
    print(f"Using data directory: {os.path.abspath(DATA_DIR)}")
    print(f"Loaded {len(get_vehicle_map())} vehicles from index.json")
    start_health_server()

    if not TOKEN:
        print("No DISCORD_TOKEN found in .env file.")
        raise SystemExit(1)

    if not acquire_instance_lock():
        raise SystemExit(1)

    retry_delay = 15
    max_retry_delay = 3600
    while True:
        try:
            app_state.bot.run(TOKEN)
            break
        except discord.LoginFailure as error:
            print(f"Discord login failed (token issue): {error}")
            break
        except discord.HTTPException as error:
            error_text = str(error)
            if '1015' in error_text or 'You are being rate limited' in error_text:
                retry_delay = max(retry_delay, 900)
                print(f"Cloudflare/Discord rate-limit block detected. Retrying in {retry_delay}s...")
            else:
                print(f"Discord HTTP error on startup: {error}. Retrying in {retry_delay}s...")
        except Exception as error:
            print(f"Unexpected bot startup error: {error}. Retrying in {retry_delay}s...")

        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, max_retry_delay)
