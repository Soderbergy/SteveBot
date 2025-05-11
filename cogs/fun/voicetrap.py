import discord
from discord.ext import commands
from discord import app_commands
import logging

logger = logging.getLogger("S.T.E.V.E")

class VoiceTrap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.traps = {}  # key: target user ID, value: (setter ID, source channel ID, destination channel ID)

    @app_commands.command(name="voicetrap", description="Trap a target user: when they join your channel, everyone else is moved.")
    @app_commands.describe(target_user="The user to trap", destination_channel="Channel to move users to")
    async def voicetrap(self, interaction: discord.Interaction, target_user: discord.Member, destination_channel: discord.VoiceChannel):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("You must be in a voice channel to set a trap!", ephemeral=True)
            logger.warning(f"{interaction.user.display_name} tried to set a trap without being in a voice channel.")
            return

        self.traps[target_user.id] = (
            interaction.user.id,
            interaction.user.voice.channel.id,
            destination_channel.id
        )
        await interaction.response.send_message(
            f"Trap set on {target_user.mention}! When they join your channel, everyone else will be moved to {destination_channel.name}.",
            ephemeral=True
        )
        logger.info(f"Trap set by {interaction.user.display_name} on {target_user.display_name}: from {interaction.user.voice.channel.name} to {destination_channel.name}")

    async def handle_voice_state_update(self, member, before, after):
        if member.id not in self.traps:
            return

        setter_id, source_channel_id, destination_channel_id = self.traps[member.id]

        if after.channel and after.channel.id == source_channel_id:
            logger.info(f"{member.display_name} triggered a voice trap in {after.channel.name}")
            destination_channel = discord.utils.get(member.guild.voice_channels, id=destination_channel_id)
            for m in after.channel.members:
                if m.id != member.id:
                    try:
                        await m.move_to(destination_channel)
                        logger.info(f"Moved {m.display_name} to {destination_channel.name}")
                    except Exception as e:
                        logger.error(f"Failed to move {m.display_name}: {e}")
            del self.traps[member.id]  # one-time use

async def setup(bot):
    await bot.add_cog(VoiceTrap(bot))
