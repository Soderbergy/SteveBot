import discord
from discord.ext import commands
import logging

logger = logging.getLogger("S.T.E.V.E")

CLIPS_CHANNEL_ID = 805084244484423680 

class ClipsOnly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.id != CLIPS_CHANNEL_ID:
            return

        has_links = any(part.startswith(("http://", "https://")) for part in message.content.split())
        has_attachments = bool(message.attachments)

        if not has_links and not has_attachments:
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention} Clips only buster. 🚫🗣️", delete_after=5)
                logger.info(f"Deleted non-clip message from {message.author.display_name}")
            except Exception as e:
                logger.warning(f"Failed to delete message in clips-only: {e}")

async def setup(bot):
    await bot.add_cog(ClipsOnly(bot))