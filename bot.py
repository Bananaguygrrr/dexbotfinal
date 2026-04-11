import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import random
import os
import asyncio
from dotenv import load_dotenv
import re
import colorsys
import time

# aiohttp is already imported by discord or in specific functions if needed

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Ensure output is flushed for the web dashboard
import sys
import builtins


def print_flush(*args, **kwargs):
    builtins.print(*args, **kwargs)
    sys.stdout.flush()


print = print_flush

# Spawning threshold
SPAWN_THRESHOLD = 5
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

USER_INVENTORIES_FILE = os.path.join(DATA_DIR, 'user_inventories.json')
IMAGES_DIR = os.path.join(DATA_DIR, 'images')
INDEX_JSON_FILE = os.path.join(DATA_DIR, 'index.json')
ROOT_INDEX_JSON_FILE = 'index.json'
FALLBACK_IMAGE_DIRS = ['images', os.path.join('static', 'images')]

if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)


def load_inventories():
    if os.path.exists(USER_INVENTORIES_FILE):
        try:
            with open(USER_INVENTORIES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {USER_INVENTORIES_FILE}: {e}")
            return {}
    return {}


def save_inventories(inventories):
    try:
        with open(USER_INVENTORIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(inventories, f, indent=4)
    except Exception as e:
        print(f"Error saving {USER_INVENTORIES_FILE}: {e}")


def add_to_inventory(user_id, vehicle_name):
    inventories = load_inventories()
    user_id_str = str(user_id)
    if user_id_str not in inventories:
        inventories[user_id_str] = []
    # User might want duplicates, let's keep them as a list
    inventories[user_id_str].append(vehicle_name)
    save_inventories(inventories)
    return True


guild_msg_counts = {}
active_spawns = {}

# Rarity weights as specified
RARITY_WEIGHTS = {
    "limited edition": 1,
    "exotic": 5,
    "legendary": 10,
    "epic": 20,
    "rare": 30,
    "common": 34
}

# Rarity colors
RARITY_COLORS = {
    "limited edition": 0x8B0000,  # Dark Red
    "exotic": 0xFF00FF,  # Exotic Magenta
    "legendary": 0xFFD700,  # Gold
    "epic": 0x800080,  # Purple
    "rare": 0x0000FF,  # Blue
    "common": 0x808080  # Grey
}


def get_random_vehicle(vehicles):
    """Pick a random vehicle based on rarity percentages, only if it has an image."""
    if not vehicles:
        return None

    # Filter to only vehicles that have a local image or valid URL
    spawnable = {k: v for k, v in vehicles.items() if
                 v.get('local_path') or (v.get('url') and str(v['url']).startswith('http'))}

    if not spawnable:
        return None

    # Group spawnable vehicles by rarity
    by_rarity = {}
    for name, data in spawnable.items():
        r = data.get('rarity', 'Common').lower()
        if r not in by_rarity:
            by_rarity[r] = []
        by_rarity[r].append(name)

    # Filter out rarities with no vehicles
    available_rarities = [r for r in RARITY_WEIGHTS.keys() if r in by_rarity]
    weights = [RARITY_WEIGHTS[r] for r in available_rarities]

    if not available_rarities:
        # Fallback to pure random choice from spawnable if no matching rarities found
        return random.choice(list(spawnable.keys()))

    selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
    return random.choice(by_rarity[selected_rarity])


# Load vehicle data
def load_vehicles():
    try:
        index_path = INDEX_JSON_FILE if os.path.exists(INDEX_JSON_FILE) else ROOT_INDEX_JSON_FILE
        if not os.path.exists(index_path):
            return {}
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        processed = {}
        for k, v in data.items():
            # Basic data normalization
            if isinstance(v, dict):
                v_data = {
                    "url": v.get('url') or v.get('pic_link'),
                    "rarity": v.get('rarity', 'Common')
                }
            else:
                v_data = {"url": str(v), "rarity": "Common"}

            # Check for local file (vehicle_name.png, jpg, etc.)
            local_path = None
            image_search_dirs = [IMAGES_DIR] + FALLBACK_IMAGE_DIRS
            for ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                for img_dir in image_search_dirs:
                    test_path = os.path.join(img_dir, f"{k}.{ext}")
                    if os.path.exists(test_path):
                        local_path = test_path
                        break
                if local_path:
                    break

            if local_path:
                v_data['local_path'] = local_path

            # Keep all entries so they can be listed/updated
            processed[k] = v_data

        return processed
    except Exception as e:
        print(f"Error loading index.json: {e}")
        return {}


vehicles = load_vehicles()
print(f"Loaded {len(vehicles)} vehicles from index.json")


def normalize_name(name):
    """Normalize name for flexible matching: lowercase and remove non-alphanumeric chars."""
    if not name:
        return ""
    # Lowercase and remove non-alphanumeric
    s = re.sub(r'[^a-z0-9]', '', name.lower())
    # Collapse consecutive identical characters: e.g. "marasetti" -> "maraseti"
    return re.sub(r'(.)\1+', r'\1', s)


class CatchModal(discord.ui.Modal, title='Catch the MT vehicle!'):
    guess = discord.ui.TextInput(
        label='What is the name of this MT vehicle?',
        placeholder='Enter your guess here...',
        required=True,
        min_length=1,
        max_length=100
    )

    def __init__(self, correct_name, vehicle_code, view):
        super().__init__()
        self.correct_name = correct_name
        self.vehicle_code = vehicle_code
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        if self.view.caught:
            await interaction.response.send_message("This MT vehicle has already been caught!", ephemeral=True)
            return

        user_guess = normalize_name(self.guess.value)
        target_name = normalize_name(self.correct_name)

        if user_guess == target_name:
            self.view.caught = True
            # Save to user inventory
            add_to_inventory(interaction.user.id, self.correct_name)

            # Update all original messages to remove the button and update text
            await self.view.update_all_messages(
                f"Congratulations! {interaction.user.name} caught the {self.correct_name}!")

            display_code = self.vehicle_code.split(',')[0].strip() if isinstance(self.vehicle_code, str) else str(
                self.vehicle_code)
            await interaction.response.send_message(
                f'{interaction.user.mention} You caught **{self.correct_name}**! `{display_code}`', ephemeral=False)

            # Reset message counter and spawn new vehicle immediately
            if interaction.guild:
                guild_msg_counts[interaction.guild.id] = 0
                await spawn_in_guild(interaction.guild)

            self.view.stop()
        else:
            await interaction.response.send_message(f'{interaction.user.mention} Wrong name!', ephemeral=False)


class CatchView(discord.ui.View):
    def __init__(self, vehicle_name, vehicle_code, image_url, rarity):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.vehicle_name = vehicle_name
        self.vehicle_code = vehicle_code
        self.image_url = image_url
        self.rarity = rarity.lower()
        self.caught = False
        self.messages = []
        self.header = "A wild MT vehicle has appeared!"

        if self.rarity == 'exotic':
            self.hue = 0.0

    def add_message(self, message):
        self.messages.append(message)

    async def update_all_messages(self, header=None, color=None):
        if header:
            self.header = header

        # Disable the catch button instead of removing it
        if self.caught or "escaped" in self.header:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

        if color is None:
            color_value = RARITY_COLORS.get(self.rarity, 0x0000FF)  # Default to blue if unknown
            color = discord.Color(color_value)

        embed = discord.Embed(title=self.header, color=color)
        embed.set_image(url=self.image_url)

        for msg in self.messages:
            try:
                await msg.edit(content=None, embed=embed, view=self)
            except Exception:
                pass

    async def on_timeout(self):
        # Called when the 5-minute window expires
        if not self.caught:
            await self.update_all_messages("The wild MT vehicle escaped! ⏳")
            self.stop()

    @discord.ui.button(label='Catch me!', style=discord.ButtonStyle.primary)
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.caught:
            await interaction.response.send_message("This MT vehicle has already been caught!", ephemeral=True)
            return

        await interaction.response.send_modal(CatchModal(self.vehicle_name, self.vehicle_code, self))


async def spawn_vehicle(vehicles, channel, guild=None, ctx=None):
    """Helper to spawn a vehicle in a specific channel/guild or ctx."""
    if not vehicles:
        if ctx: await ctx.send("No vehicles available.")
        return False

    # Update active spawn tracking if in a guild
    target_guild = guild or (ctx.guild if ctx else None)
    if target_guild:
        # Despawn previous if it exists
        if target_guild.id in active_spawns:
            old_view = active_spawns[target_guild.id]
            if not old_view.caught:
                await old_view.update_all_messages("The wild MT vehicle escaped! ⏳")
                old_view.stop()

    vehicle_name = get_random_vehicle(vehicles)
    if not vehicle_name:
        return False

    vehicle_data = vehicles[vehicle_name]
    local_path = vehicle_data.get('local_path')
    image_url = vehicle_data.get('url')
    vehicle_code = vehicle_data.get('code', vehicle_data.get('rarity', 'Common'))
    rarity = vehicle_data.get('rarity', 'Common')

    # If local file exists, we'll use attachment protocol
    display_url = image_url
    file = None
    if local_path:
        file = discord.File(local_path, filename="vehicle.png")
        display_url = "attachment://vehicle.png"

    print(f"Spawning vehicle: {vehicle_name} | Rarity: {rarity} | Local: {local_path is not None}")

    view = CatchView(vehicle_name, vehicle_code, display_url, rarity)

    if target_guild:
        active_spawns[target_guild.id] = view

    try:
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.embed_links:
            print(f"Warning: Bot lacks 'Embed Links' permission in {channel.guild.name}#{channel.name}")
            if ctx: await ctx.send("Bot lacks 'Embed Links' permission.")
            return False

        color_value = RARITY_COLORS.get(rarity.lower(), 0x00FF00)  # Default to green if unknown for appearance
        embed = discord.Embed(title="A wild MT vehicle has appeared!", color=discord.Color(color_value))
        embed.set_image(url=display_url)

        if ctx:
            sent = await ctx.send(embed=embed, file=file, view=view)
        else:
            sent = await channel.send(embed=embed, file=file, view=view)

        view.add_message(sent)
        return True  # Successfully spawned
    except Exception as e:
        print(f"Error sending vehicle message: {e}")

    return False


async def spawn_in_guild(guild):
    """Spawns a vehicle in a specific guild."""
    global vehicles
    vehicles = load_vehicles()  # Refresh vehicles to pick up website changes

    # Try to find 'mt-dex' channel, or fallback to the first available text channel
    channel = discord.utils.get(guild.text_channels, name='mt-dex')
    if not channel and guild.text_channels:
        channel = guild.text_channels[0]

    if channel:
        await spawn_vehicle(vehicles, channel, guild=guild)
    else:
        print(f"No suitable channel found in {guild.name}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Handle !inv / !inventory prefix commands
    if message.content.lower() in ['!inv', '!inventory']:
        view = InventoryOverview(message.author.id)
        embed = create_overview_embed(message.author)
        await message.channel.send(embed=embed, view=view)
        return

    # Handle !help prefix command
    if message.content.lower() in ['!help', '!h']:
        help_text = (
            "**MT Vehicle Bot Commands:**\n"
            "`/show` - Show a vehicle's picture and rarity\n"
            "`!inventory` or `!inv` - View your caught vehicles\n"
            "`/inventory` - Slash command version of inventory\n"
            "`!sync` - Manually sync slash commands (if they are missing)\n\n"
            "*Vehicles spawn automatically every 5 messages!*"
        )
        await message.channel.send(help_text)
        return

    # Handle !sync prefix command
    if message.content.lower() == '!sync':
        try:
            synced = await bot.tree.sync()
            await message.channel.send(f"Synced {len(synced)} slash command(s) successfully!")
        except Exception as e:
            await message.channel.send(f"Error syncing slash commands: {e}")
        return

    if message.guild:
        guild_id = message.guild.id
        # Increment message count for this guild
        guild_msg_counts[guild_id] = guild_msg_counts.get(guild_id, 0) + 1

        if guild_msg_counts[guild_id] >= SPAWN_THRESHOLD:
            guild_msg_counts[guild_id] = 0
            await spawn_in_guild(message.guild)


@tasks.loop(seconds=1)
async def rainbow_task():
    """Centralized task to cycle colors for all active exotic vehicles."""
    update_tasks = []
    for guild_id in list(active_spawns.keys()):
        view = active_spawns[guild_id]
        if not view.is_finished() and not view.caught and view.rarity == 'exotic':
            if view.messages:
                hue = getattr(view, 'hue', 0.0)
                rgb = colorsys.hsv_to_rgb(hue, 1, 1)
                color = discord.Color.from_rgb(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
                update_tasks.append(view.update_all_messages(color=color))
                view.hue = (hue + 0.2) % 1.0

    if update_tasks:
        await asyncio.gather(*update_tasks, return_exceptions=True)


def create_overview_embed(user):
    inventories = load_inventories()
    user_inventory = inventories.get(str(user.id), [])

    counts = {r: 0 for r in RARITY_WEIGHTS.keys()}
    for v_name in user_inventory:
        if v_name in vehicles:
            r = vehicles[v_name]['rarity'].lower()
            if r in counts:
                counts[r] += 1

    embed = discord.Embed(title=f"{user.name}'s Inventory", color=discord.Color.blue())
    desc = ""
    for rarity, count in counts.items():
        desc += f"**{rarity.title()}:** {count}\n"
    embed.description = desc or "You haven't caught any vehicles yet!"
    return embed


def get_user_rarity_vehicle_counts(user_id, rarity):
    inventories = load_inventories()
    user_inventory = inventories.get(str(user_id), [])
    counts = {}
    for v_name in user_inventory:
        if v_name in vehicles and vehicles[v_name].get('rarity', 'Common').lower() == rarity:
            counts[v_name] = counts.get(v_name, 0) + 1
    return counts


class RarityButton(discord.ui.Button):
    def __init__(self, rarity, label, style, disabled):
        super().__init__(label=label, style=style, disabled=disabled)
        self.rarity = rarity

    async def callback(self, interaction: discord.Interaction):
        view = RarityInventoryView(interaction.user.id, self.rarity)
        embed = view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class InventoryOverview(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=120)
        self.user_id = user_id

        inventories = load_inventories()
        user_inventory = inventories.get(str(user_id), [])

        counts = {r: 0 for r in RARITY_WEIGHTS.keys()}
        for v_name in user_inventory:
            if v_name in vehicles:
                r = vehicles[v_name]['rarity'].lower()
                if r in counts:
                    counts[r] += 1

        # Add buttons for each rarity
        for rarity in RARITY_WEIGHTS.keys():
            count = counts[rarity]
            style = discord.ButtonStyle.secondary
            if rarity == 'limited edition':
                style = discord.ButtonStyle.danger
            elif rarity == 'exotic':
                style = discord.ButtonStyle.success
            elif rarity == 'legendary':
                style = discord.ButtonStyle.primary

            self.add_item(RarityButton(rarity, f"{rarity.title()}", style, count == 0))


class RarityInventoryView(discord.ui.View):
    def __init__(self, user_id, rarity):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.rarity = rarity
        self.vehicle_counts = get_user_rarity_vehicle_counts(user_id, rarity)

        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        view = InventoryOverview(interaction.user.id)
        embed = create_overview_embed(interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)

    def create_embed(self):
        color_value = RARITY_COLORS.get(self.rarity, 0x0000FF)
        embed = discord.Embed(title=f"Your {self.rarity.title()} Vehicles", color=discord.Color(color_value))
        if not self.vehicle_counts:
            embed.description = "You haven't caught any vehicles of this rarity yet."
        else:
            sorted_items = sorted(self.vehicle_counts.items(), key=lambda item: (-item[1], item[0].lower()))
            lines = [f"- {name} x{count}" for name, count in sorted_items[:30]]
            total_unique = len(sorted_items)
            total_caught = sum(self.vehicle_counts.values())
            embed.description = "\n".join(lines)
            embed.set_footer(text=f"Unique: {total_unique} | Total caught: {total_caught}")
            if total_unique > 30:
                embed.description += f"\n...and {total_unique - 30} more"
        return embed


@bot.tree.command(name="inventory", description="View your vehicle inventory")
async def inventory_slash(interaction: discord.Interaction):
    view = InventoryOverview(interaction.user.id)
    embed = create_overview_embed(interaction.user)
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="show", description="Show a vehicle's picture and rarity")
@app_commands.describe(vehicle_name="The name of the vehicle to show")
async def show_vehicle(interaction: discord.Interaction, vehicle_name: str):
    # If the exact match doesn't exist, try a case-insensitive match
    if vehicle_name not in vehicles:
        matching_names = [n for n in vehicles.keys() if n.lower() == vehicle_name.lower()]
        if matching_names:
            vehicle_name = matching_names[0]
        else:
            await interaction.response.send_message(f"❌ Vehicle **{vehicle_name}** not found.", ephemeral=True)
            return

    vehicle_data = vehicles[vehicle_name]
    rarity = vehicle_data.get('rarity', 'Common')
    local_path = vehicle_data.get('local_path')
    image_url = vehicle_data.get('url')

    color_value = RARITY_COLORS.get(rarity.lower(), 0x808080)
    embed = discord.Embed(title=vehicle_name, color=discord.Color(color_value))
    embed.add_field(name="Rarity", value=rarity.title(), inline=True)

    file = None
    if local_path:
        file = discord.File(local_path, filename="vehicle.png")
        embed.set_image(url="attachment://vehicle.png")
    elif image_url and str(image_url).startswith('http'):
        embed.set_image(url=image_url)
    else:
        embed.description = "This vehicle has no picture yet."

    if file:
        await interaction.response.send_message(embed=embed, file=file)
    else:
        await interaction.response.send_message(embed=embed)


@show_vehicle.autocomplete('vehicle_name')
async def show_vehicle_autocomplete(interaction: discord.Interaction, current: str):
    # Show existing names from vehicles dict
    names = list(vehicles.keys())
    return [
        app_commands.Choice(name=name, value=name)
        for name in names if current.lower() in name.lower()
    ][:25]


@bot.event
async def on_ready():
    print(f'Bot is logged in as {bot.user.name}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing tree: {e}")

    if not rainbow_task.is_running():
        rainbow_task.start()


if __name__ == '__main__':
    if TOKEN:
        retry_delay = 15
        max_retry_delay = 3600
        while True:
            try:
                bot.run(TOKEN)
                break
            except discord.LoginFailure as e:
                print(f"Discord login failed (token issue): {e}")
                break
            except discord.HTTPException as e:
                # Handles temporary API/CDN blocks (e.g., Cloudflare 1015) without crashing the service.
                error_text = str(e)
                if '1015' in error_text or 'You are being rate limited' in error_text:
                    retry_delay = max(retry_delay, 900)
                    print(f"Cloudflare/Discord rate-limit block detected. Retrying in {retry_delay}s...")
                else:
                    print(f"Discord HTTP error on startup: {e}. Retrying in {retry_delay}s...")
            except Exception as e:
                print(f"Unexpected bot startup error: {e}. Retrying in {retry_delay}s...")

            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)
    else:
        print("No DISCORD_TOKEN found in .env file.")
