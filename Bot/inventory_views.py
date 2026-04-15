import discord

from config import RARITY_COLORS, RARITY_WEIGHTS
from storage import load_inventories
from utils import format_count
from vehicle_data import get_vehicle_map


def create_overview_embed(user):
    inventories = load_inventories()
    user_inventory = inventories.get(str(user.id), {})
    vehicles = get_vehicle_map()

    counts = {rarity: 0 for rarity in RARITY_WEIGHTS}
    for vehicle_name, count in user_inventory.items():
        if vehicle_name in vehicles:
            rarity = vehicles[vehicle_name]['rarity'].lower()
            if rarity in counts:
                counts[rarity] += count

    embed = discord.Embed(title=f"{user.name}'s Inventory", color=discord.Color.blue())
    embed.description = "".join(
        f"**{rarity.title()}:** {format_count(count)}\n"
        for rarity, count in counts.items()
    ) or "You haven't caught any vehicles yet!"
    return embed


def get_user_rarity_vehicle_counts(user_id, rarity):
    inventories = load_inventories()
    user_inventory = inventories.get(str(user_id), {})
    vehicles = get_vehicle_map()
    counts = {}
    for vehicle_name, count in user_inventory.items():
        if vehicle_name in vehicles and vehicles[vehicle_name].get('rarity', 'Common').lower() == rarity:
            counts[vehicle_name] = count
    return counts


class RarityButton(discord.ui.Button):
    def __init__(self, user, rarity, label, style, disabled, owner):
        super().__init__(label=label, style=style, disabled=disabled)
        self.user = user
        self.rarity = rarity
        self.owner = owner

    async def callback(self, interaction: discord.Interaction):
        view = RarityInventoryView(self.user, self.rarity, self.owner)
        await interaction.response.edit_message(embed=view.create_embed(), view=view)


class InventoryOverview(discord.ui.View):
    def __init__(self, user, owner):
        super().__init__(timeout=120)
        self.user = user
        self.owner = owner

        inventories = load_inventories()
        user_inventory = inventories.get(str(user.id), {})
        vehicles = get_vehicle_map()

        counts = {rarity: 0 for rarity in RARITY_WEIGHTS}
        for vehicle_name, count in user_inventory.items():
            if vehicle_name in vehicles:
                rarity = vehicles[vehicle_name]['rarity'].lower()
                if rarity in counts:
                    counts[rarity] += count

        for rarity in RARITY_WEIGHTS:
            count = counts[rarity]
            style = discord.ButtonStyle.secondary
            if rarity == 'limited edition':
                style = discord.ButtonStyle.danger
            elif rarity == 'exotic':
                style = discord.ButtonStyle.success
            elif rarity == 'legendary':
                style = discord.ButtonStyle.primary
            self.add_item(RarityButton(user, rarity, rarity.title(), style, count == 0, owner))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("Only the person who used the command can use these buttons!", ephemeral=True)
            return False
        return True


class RarityInventoryView(discord.ui.View):
    def __init__(self, user, rarity, owner):
        super().__init__(timeout=120)
        self.user = user
        self.rarity = rarity
        self.owner = owner
        self.vehicle_counts = get_user_rarity_vehicle_counts(user.id, rarity)

        back_button = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary)
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def back_callback(self, interaction: discord.Interaction):
        view = InventoryOverview(self.user, self.owner)
        await interaction.response.edit_message(embed=create_overview_embed(self.user), view=view)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("Only the person who used the command can use these buttons!", ephemeral=True)
            return False
        return True

    def create_embed(self):
        color_value = RARITY_COLORS.get(self.rarity, 0x0000FF)
        embed = discord.Embed(
            title=f"{self.user.name}'s {self.rarity.title()} Vehicles",
            color=discord.Color(color_value)
        )
        if not self.vehicle_counts:
            embed.description = "You haven't caught any vehicles of this rarity yet."
            return embed

        sorted_items = sorted(self.vehicle_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        lines = [f"- {format_count(count)} | {name.replace('-', '')}" for name, count in sorted_items[:30]]
        total_unique = len(sorted_items)
        total_caught = sum(self.vehicle_counts.values())
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Unique: {total_unique} | Total caught: {format_count(total_caught)}")
        if total_unique > 30:
            embed.description += f"\n...and {total_unique - 30} more"
        return embed
