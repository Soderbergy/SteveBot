import discord
from discord.ext import commands
from discord import app_commands
import random
import logging

logger = logging.getLogger("S.T.E.V.E")

class WhoAsked(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="whoasked", description="Finds out who asked.")
    async def whoasked(self, interaction: discord.Interaction):
        await interaction.response.defer()

        channel = interaction.channel
        messages = [msg async for msg in channel.history(limit=50)]

        candidates = list({msg.author for msg in messages if msg.author != interaction.user and not msg.author.bot})

        if not candidates:
            await interaction.followup.send("I scanned the whole channel... nobody asked. Shocking.")
            logger.info(f"{interaction.user.display_name} used /whoasked but no one was found.")
            return

        target = random.choice(candidates)
        responses = [
            f"After careful analysis, the one who asked... was **{target.display_name}**.",
            f"It was foretold in the scrolls... **{target.display_name}** asked.",
            f"I reviewed the logs. Yep, definitely **{target.display_name}**.",
            f"I have seen the truth. The asker is **{target.display_name}**.",
            f"Behold! The one who asked... was **{target.display_name}**."
        ]
        response = random.choice(responses)
        await interaction.followup.send(response)
        logger.info(f"{interaction.user.display_name} used /whoasked — blamed {target.display_name}.")

async def setup(bot):
    await bot.add_cog(WhoAsked(bot))