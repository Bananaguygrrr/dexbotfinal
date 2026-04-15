import asyncio
import colorsys

import discord
from discord.ext import tasks

import app_state
from config import RARITY_COLORS, SPAWN_THRESHOLD
from storage import add_to_inventory
from utils import normalize_name
from vehicle_data import get_random_vehicle, refresh_vehicles


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

        if normalize_name(self.guess.value) == normalize_name(self.correct_name):
            self.view.caught = True
            display_code = self.vehicle_code.split(',')[0].strip() if isinstance(self.vehicle_code, str) else str(self.vehicle_code)
            await interaction.response.send_message(
                f'{interaction.user.mention} You caught **{self.correct_name.replace("-", "")}**! `{display_code}`',
                ephemeral=False
            )
            add_to_inventory(interaction.user.id, self.correct_name)
            await self.view.update_all_messages(
                f"Congratulations! {interaction.user.name} caught the {self.correct_name.replace('-', '')}!"
            )
            self.view.stop()
        else:
            await interaction.response.send_message(f'{interaction.user.mention} Wrong name!', ephemeral=False)


class CatchView(discord.ui.View):
    def __init__(self, vehicle_name, vehicle_code, image_url, rarity):
        super().__init__(timeout=SPAWN_THRESHOLD * 60)
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

        if self.caught or "escaped" in self.header:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

        if color is None:
            color = discord.Color(RARITY_COLORS.get(self.rarity, 0x0000FF))

        embed = discord.Embed(title=self.header, color=color)
        embed.set_image(url=self.image_url)

        for message in self.messages:
            try:
                await message.edit(content=None, embed=embed, view=self)
            except Exception:
                pass

    async def on_timeout(self):
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
    if not vehicles:
        if ctx:
            await ctx.send("No vehicles available.")
        return False

    target_guild = guild or (ctx.guild if ctx else None)
    if target_guild and target_guild.id in app_state.active_spawns:
        old_view = app_state.active_spawns[target_guild.id]
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

    display_url = image_url
    file = None
    if not (image_url and str(image_url).startswith('http')) and local_path:
        file = discord.File(local_path, filename="vehicle.png")
        display_url = "attachment://vehicle.png"

    print(f"Spawning vehicle: {vehicle_name} | Rarity: {rarity} | Remote: {bool(image_url and str(image_url).startswith('http'))} | Local: {local_path is not None}")

    view = CatchView(vehicle_name, vehicle_code, display_url, rarity)
    if target_guild:
        app_state.active_spawns[target_guild.id] = view

    try:
        permissions = channel.permissions_for(channel.guild.me)
        if not permissions.embed_links:
            print(f"Warning: Bot lacks 'Embed Links' permission in {channel.guild.name}#{channel.name}")
            if ctx:
                await ctx.send("Bot lacks 'Embed Links' permission.")
            return False

        embed = discord.Embed(
            title="A wild MT vehicle has appeared!",
            color=discord.Color(RARITY_COLORS.get(rarity.lower(), 0x00FF00))
        )
        embed.set_image(url=display_url)

        sent = await (ctx.send(embed=embed, file=file, view=view) if ctx else channel.send(embed=embed, file=file, view=view))
        view.add_message(sent)
        return True
    except Exception as error:
        print(f"Error sending vehicle message: {error}")
        return False


async def spawn_in_guild(guild):
    vehicles = refresh_vehicles()
    channel = discord.utils.get(guild.text_channels, name='mt-dex')
    if not channel and guild.text_channels:
        channel = guild.text_channels[0]

    if channel:
        await spawn_vehicle(vehicles, channel, guild=guild)
    else:
        print(f"No suitable channel found in {guild.name}")


@tasks.loop(seconds=1)
async def rainbow_task():
    update_tasks = []
    for guild_id in list(app_state.active_spawns.keys()):
        view = app_state.active_spawns[guild_id]
        if not view.is_finished() and not view.caught and view.rarity == 'exotic' and view.messages:
            hue = getattr(view, 'hue', 0.0)
            rgb = colorsys.hsv_to_rgb(hue, 1, 1)
            color = discord.Color.from_rgb(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
            update_tasks.append(view.update_all_messages(color=color))
            view.hue = (hue + 0.2) % 1.0

    if update_tasks:
        await asyncio.gather(*update_tasks, return_exceptions=True)
