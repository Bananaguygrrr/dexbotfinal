import time

import discord
from discord.ext import commands


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

BOT_ONLINE = False
BOT_STARTED_AT = int(time.time())
INSTANCE_LOCK_HANDLE = None

guild_msg_counts = {}
active_spawns = {}
pending_trades = {}
active_trades = {}
