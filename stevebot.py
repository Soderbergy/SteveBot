import discord
from discord.ext import commands
from discord import app_commands
import os
import logging
from dotenv import load_dotenv
import coloredlogs
import asyncio
load_dotenv()

logger = logging.getLogger("S.T.E.V.E")

level_styles = {
    'info': {'color': 'green'},
    'error': {'color': 'red', 'bold': True},
    'warning': {'color': 'yellow'},
    'debug': {'color': 'cyan'},
    'critical': {'color': 'magenta', 'bold': True}
}

field_styles = {
    'asctime': {'color': 'blue'},
    'levelname': {'bold': True},
    'name': {'color': 'white'},
    'message': {'color': 'white'}
}

coloredlogs.install(
    level='INFO',
    logger=logger,
    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level_styles=level_styles,
    field_styles=field_styles
)

intents = discord.Intents.default()
intents.message_content = True  # Still needed for reading messages, even with slash commands

bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree  # This lets us define slash commands

@bot.event
async def on_ready():
    await tree.sync()  # Registers slash commands globally
    logger.info(f"S.T.E.V.E is online as {bot.user}!")

@bot.event
async def on_voice_state_update(member, before, after):
    cog = bot.get_cog("VoiceTrap")
    if cog:
        await cog.handle_voice_state_update(member, before, after)

@bot.event
async def setup_hook():
    for root, dirs, files in os.walk("cogs"):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                ext_path = os.path.join(root, file).replace("/", ".").replace("\\", ".")[:-3]
                logger.info(f"Attempting to load: {ext_path}")
                try:
                    await bot.load_extension(ext_path)
                    logger.info(f"Loaded extension: {ext_path}")
                except Exception as e:
                    logger.error(f"Failed to load {ext_path}: {e}")

bot.run(os.getenv("STEVE_TOKEN"))