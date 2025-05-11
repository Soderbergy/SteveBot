import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
import json
import os

logger = logging.getLogger("S.T.E.V.E")

OPERATORS = {}

class OpRoulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.load_operators()

    def load_operators(self):
        try:
            with open(os.path.join("data", "operators.json"), "r") as f:
                global OPERATORS
                OPERATORS = json.load(f)
                logger.info("Operator data loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load operator data: {e}")
            OPERATORS.clear()

    @app_commands.command(name="oproulette", description="Get a random valid operator loadout.")
    @app_commands.describe(role="Choose attacker or defender")
    async def oproulette(self, interaction: discord.Interaction, role: str):
        role = role.lower()
        if role not in OPERATORS:
            await interaction.response.send_message("Please choose either 'attacker' or 'defender'.", ephemeral=True)
            return

        operator = random.choice(list(OPERATORS[role].keys()))
        loadout = OPERATORS[role][operator]

        primary = random.choice(loadout["primary"])
        secondary = random.choice(loadout["secondary"])
        gadget = random.choice(loadout["gadget"])

        logger.info(f"{interaction.user.display_name} rolled {operator} ({role}): {primary}, {secondary}, {gadget}")

        embed = discord.Embed(title="🎲 Operator Roulette", color=discord.Color.blurple())
        embed.add_field(name="Operator", value=operator, inline=False)
        embed.add_field(name="Primary", value=primary, inline=True)
        embed.add_field(name="Secondary", value=secondary, inline=True)
        embed.add_field(name="Gadget", value=gadget, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(OpRoulette(bot))
