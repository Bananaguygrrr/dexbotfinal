import asyncio

import discord
from discord import app_commands

import app_state
from inventory_views import InventoryOverview, create_overview_embed
from storage import load_inventories, save_inventories
from utils import format_count, parse_count, safe_defer, safe_send
from vehicle_data import find_best_vehicle_match


def get_active_trade_for_user(user_id):
    trade_view = app_state.active_trades.get(user_id)
    if not trade_view or trade_view.cancelled or trade_view.completed:
        return None
    return trade_view


def get_trade_offer_for_user(trade_view, user_id):
    if user_id == trade_view.user_a.id:
        return trade_view.offer_a
    if user_id == trade_view.user_b.id:
        return trade_view.offer_b
    return None


def get_trade_available_vehicles(user_id):
    trade_view = get_active_trade_for_user(user_id)
    if not trade_view:
        return {}

    inventories = load_inventories()
    user_inventory = inventories.get(str(user_id), {})
    current_offer = get_trade_offer_for_user(trade_view, user_id) or {}

    available = {}
    for vehicle_name, owned_count in user_inventory.items():
        remaining = owned_count - current_offer.get(vehicle_name, 0)
        if remaining > 0:
            available[vehicle_name] = remaining
    return available


class TradeView(discord.ui.View):
    def __init__(self, user_a, user_b):
        super().__init__(timeout=600)
        self.user_a = user_a
        self.user_b = user_b
        self.offer_a = {}
        self.offer_b = {}
        self.ready_a = False
        self.ready_b = False
        self.cancelled = False
        self.completed = False
        self.cancelled_by = None
        self.message = None
        self.countdown_task = None
        self.countdown_remaining = 0

    def create_embed(self):
        embed = discord.Embed(title="🤝 Vehicle Trade", color=discord.Color.gold())

        def format_offer(offer):
            if not offer:
                return "*No vehicles added yet*"
            return "\n".join(f"- {format_count(count)} | {name.replace('-', '')}" for name, count in offer.items())

        embed.add_field(name=f"{self.user_a.name}'s Offer", value=format_offer(self.offer_a), inline=True)
        embed.add_field(name=f"{self.user_b.name}'s Offer", value=format_offer(self.offer_b), inline=True)

        status_a = "✅ READY" if self.ready_a else "⏳ Not Ready"
        status_b = "✅ READY" if self.ready_b else "⏳ Not Ready"
        status_text = f"**{self.user_a.name}:** {status_a}\n**{self.user_b.name}:** {status_b}"
        if self.countdown_remaining > 0:
            status_text += f"\n\n🕒 **Completing in {self.countdown_remaining}s...**"
        embed.add_field(name="Status", value=status_text, inline=False)

        if self.cancelled:
            embed.title = "❌ Trade Cancelled"
            if self.cancelled_by:
                embed.description = f"**Reason:** {self.cancelled_by}"
            embed.color = discord.Color.red()
        elif self.completed:
            embed.title = "🎉 Trade Completed!"
            embed.color = discord.Color.green()

        return embed

    async def update_message(self):
        if self.cancelled or self.completed:
            if self.countdown_task and not self.countdown_task.done():
                self.countdown_task.cancel()
                self.countdown_task = None
                self.countdown_remaining = 0
            for item in self.children:
                item.disabled = True

            if app_state.active_trades.get(self.user_a.id) == self:
                del app_state.active_trades[self.user_a.id]
            if app_state.active_trades.get(self.user_b.id) == self:
                del app_state.active_trades[self.user_b.id]

        if self.message is None:
            return
        try:
            await self.message.edit(embed=self.create_embed(), view=self)
        except Exception as error:
            print(f"Error updating trade message: {error}")

    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success)
    async def ready_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user_a.id:
            self.ready_a = not self.ready_a
        elif interaction.user.id == self.user_b.id:
            self.ready_b = not self.ready_b
        else:
            await interaction.response.send_message("You are not part of this trade!", ephemeral=True)
            return

        if self.ready_a and self.ready_b:
            if not self.countdown_task or self.countdown_task.done():
                self.countdown_task = asyncio.create_task(self.countdown_loop())
        else:
            if self.countdown_task and not self.countdown_task.done():
                self.countdown_task.cancel()
                self.countdown_task = None
            self.countdown_remaining = 0

        await interaction.response.defer()
        await self.update_message()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.user_a.id, self.user_b.id]:
            await interaction.response.send_message("You are not part of this trade!", ephemeral=True)
            return
        self.cancelled = True
        self.cancelled_by = f"Cancelled by {interaction.user.name}"
        await interaction.response.defer()
        await self.update_message()
        self.stop()

    async def countdown_loop(self):
        try:
            self.countdown_remaining = 5
            while self.countdown_remaining > 0:
                await self.update_message()
                await asyncio.sleep(1)
                self.countdown_remaining -= 1

            if self.ready_a and self.ready_b and not self.cancelled and not self.completed and self.message:
                await self.complete_trade(None)
        except asyncio.CancelledError:
            pass
        finally:
            self.countdown_remaining = 0
            if not self.completed and not self.cancelled:
                await self.update_message()

    def reset_countdown(self):
        if self.countdown_task and not self.countdown_task.done():
            self.countdown_remaining = 5

    async def cancel_trade(self):
        if not self.cancelled and not self.completed:
            self.cancelled = True
            self.cancelled_by = "New trade started"
            await self.update_message()
            self.stop()

    async def on_timeout(self):
        if not self.cancelled and not self.completed:
            self.cancelled = True
            self.cancelled_by = "Trade timed out"
            await self.update_message()
            self.stop()

    async def complete_trade(self, interaction):
        inventories = load_inventories()
        inv_a = inventories.get(str(self.user_a.id), {})
        inv_b = inventories.get(str(self.user_b.id), {})

        for name, count in self.offer_a.items():
            if inv_a.get(name, 0) < count:
                channel = interaction.channel if interaction else self.message.channel
                await channel.send(f"Trade failed! {self.user_a.name} no longer has enough {name}.")
                self.cancelled = True
                self.cancelled_by = f"{self.user_a.name} missing items"
                await self.update_message()
                return

        for name, count in self.offer_b.items():
            if inv_b.get(name, 0) < count:
                channel = interaction.channel if interaction else self.message.channel
                await channel.send(f"Trade failed! {self.user_b.name} no longer has enough {name}.")
                self.cancelled = True
                self.cancelled_by = f"{self.user_b.name} missing items"
                await self.update_message()
                return

        for name, count in self.offer_a.items():
            inv_a[name] -= count
            if inv_a[name] <= 0:
                del inv_a[name]
            inv_b[name] = inv_b.get(name, 0) + count

        for name, count in self.offer_b.items():
            inv_b[name] -= count
            if inv_b[name] <= 0:
                del inv_b[name]
            inv_a[name] = inv_a.get(name, 0) + count

        inventories[str(self.user_a.id)] = inv_a
        inventories[str(self.user_b.id)] = inv_b
        save_inventories(inventories)
        self.completed = True
        await self.update_message()
        self.stop()


def register_trade_commands(bot):
    @bot.tree.command(name="inventory", description="View a vehicle inventory")
    @app_commands.describe(user="The user whose inventory you want to view")
    async def inventory_slash(interaction: discord.Interaction, user: discord.User = None):
        target_user = user or interaction.user
        view = InventoryOverview(target_user, interaction.user)
        await interaction.response.send_message(embed=create_overview_embed(target_user), view=view)

    @bot.tree.command(name="tradeadd", description="Add a vehicle to your active trade offer")
    @app_commands.guild_only()
    @app_commands.describe(vehicle_name="The vehicle to add", amount="How many to add")
    async def tradeadd_slash(interaction: discord.Interaction, vehicle_name: str, amount: str):
        if not await safe_defer(interaction, ephemeral=True):
            return
        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            await safe_send(interaction, "You don't have an active trade right now.", ephemeral=True)
            return
        if interaction.user.id not in [trade_view.user_a.id, trade_view.user_b.id]:
            await safe_send(interaction, "You are not part of this trade!", ephemeral=True)
            return

        parsed_amount = parse_count(amount)
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Please enter a positive number.", ephemeral=True)
            return

        available_vehicles = get_trade_available_vehicles(interaction.user.id)
        matched_vehicle = vehicle_name if vehicle_name in available_vehicles else find_best_vehicle_match(available_vehicles.keys(), vehicle_name)
        if not matched_vehicle:
            await safe_send(interaction, f"No vehicle matching '{vehicle_name}' found in your inventory.", ephemeral=True)
            return

        available = available_vehicles[matched_vehicle]
        if parsed_amount > available:
            await safe_send(interaction, f"You don't have enough {matched_vehicle.replace('-', '')}! Available: {format_count(available)}", ephemeral=True)
            return

        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id)
        current_offer[matched_vehicle] = current_offer.get(matched_vehicle, 0) + parsed_amount
        trade_view.reset_countdown()
        await trade_view.update_message()
        await safe_send(interaction, f"Added {format_count(parsed_amount)} | {matched_vehicle.replace('-', '')} to your offer.", ephemeral=True)

    @tradeadd_slash.autocomplete('vehicle_name')
    async def tradeadd_vehicle_autocomplete(interaction: discord.Interaction, current: str):
        available_vehicles = get_trade_available_vehicles(interaction.user.id)
        current_lower = current.lower()
        sorted_items = sorted(available_vehicles.items(), key=lambda item: (-item[1], item[0].lower()))
        return [
            app_commands.Choice(name=f"{name.replace('-', '')} ({format_count(count)} owned)", value=name)
            for name, count in sorted_items
            if not current_lower or current_lower in name.lower() or current_lower in name.lower().replace('-', '')
        ][:25]

    @bot.tree.command(name="traderemove", description="Remove a vehicle from your active trade offer")
    @app_commands.guild_only()
    @app_commands.describe(vehicle_name="The vehicle to remove", amount="How many to remove")
    async def traderemove_slash(interaction: discord.Interaction, vehicle_name: str, amount: str = "1"):
        if not await safe_defer(interaction, ephemeral=True):
            return
        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            await safe_send(interaction, "You don't have an active trade right now.", ephemeral=True)
            return
        if interaction.user.id not in [trade_view.user_a.id, trade_view.user_b.id]:
            await safe_send(interaction, "You are not part of this trade!", ephemeral=True)
            return

        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id)
        if not current_offer:
            await safe_send(interaction, "Your offer is empty!", ephemeral=True)
            return

        parsed_amount = parse_count(amount)
        if parsed_amount is None or parsed_amount <= 0:
            await safe_send(interaction, "Invalid amount. Please enter a positive number.", ephemeral=True)
            return

        matched_vehicle = vehicle_name if vehicle_name in current_offer else find_best_vehicle_match(current_offer.keys(), vehicle_name)
        if not matched_vehicle:
            await safe_send(interaction, f"No vehicle matching '{vehicle_name}' found in your current offer.", ephemeral=True)
            return

        amount_to_remove = min(parsed_amount, current_offer[matched_vehicle])
        current_offer[matched_vehicle] -= amount_to_remove
        if current_offer[matched_vehicle] <= 0:
            del current_offer[matched_vehicle]

        trade_view.reset_countdown()
        await trade_view.update_message()
        await safe_send(interaction, f"Removed {format_count(amount_to_remove)} | {matched_vehicle.replace('-', '')} from your offer.", ephemeral=True)

    @traderemove_slash.autocomplete('vehicle_name')
    async def traderemove_vehicle_autocomplete(interaction: discord.Interaction, current: str):
        trade_view = get_active_trade_for_user(interaction.user.id)
        if not trade_view:
            return []
        current_offer = get_trade_offer_for_user(trade_view, interaction.user.id) or {}
        current_lower = current.lower()
        sorted_items = sorted(current_offer.items(), key=lambda item: (-item[1], item[0].lower()))
        return [
            app_commands.Choice(name=f"{name.replace('-', '')} ({format_count(count)} in offer)", value=name)
            for name, count in sorted_items
            if not current_lower or current_lower in name.lower() or current_lower in name.lower().replace('-', '')
        ][:25]

    @bot.tree.command(name="trade", description="Send a trade request to another user")
    @app_commands.guild_only()
    @app_commands.describe(user="The user you want to trade with")
    async def trade_slash(interaction: discord.Interaction, user: discord.User):
        if not await safe_defer(interaction):
            return
        if user.id == interaction.user.id:
            await safe_send(interaction, "You cannot trade with yourself!", ephemeral=True)
            return
        if user.bot:
            await safe_send(interaction, "You cannot trade with bots!", ephemeral=True)
            return

        app_state.pending_trades[(interaction.guild.id, user.id)] = interaction.user.id
        await safe_send(
            interaction,
            f" {user.mention} , {interaction.user.mention} sent you a traderequest!\n use `/tradeaccept {interaction.user.name}` to start the trade."
        )

    @bot.tree.command(name="tradeaccept", description="Accept a trade request")
    @app_commands.guild_only()
    @app_commands.describe(user="The user whose trade request you want to accept")
    async def tradeaccept_slash(interaction: discord.Interaction, user: discord.User):
        if not await safe_defer(interaction):
            return
        guild_id = interaction.guild.id
        if (guild_id, interaction.user.id) in app_state.pending_trades and app_state.pending_trades[(guild_id, interaction.user.id)] == user.id:
            if user.id in app_state.active_trades:
                await app_state.active_trades[user.id].cancel_trade()
            if interaction.user.id in app_state.active_trades:
                await app_state.active_trades[interaction.user.id].cancel_trade()

            del app_state.pending_trades[(guild_id, interaction.user.id)]
            view = TradeView(user, interaction.user)
            app_state.active_trades[user.id] = view
            app_state.active_trades[interaction.user.id] = view
            view.message = await safe_send(
                interaction,
                f"🤝 Trade started between {user.mention} and {interaction.user.mention}!",
                embed=view.create_embed(),
                view=view,
                wait=True
            )
        else:
            await safe_send(interaction, f"❌ You don't have a pending trade request from {user.name}.", ephemeral=True)
