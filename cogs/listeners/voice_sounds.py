import discord
from discord.ext import commands
import os
import logging
from discord import app_commands

logger = logging.getLogger("S.T.E.V.E")

TARGET_CHANNEL_ID = 736816227506454532  # Replace with your VC ID
AUDIO_FILE = "assets/sounds/nuclear-diarrhea.mp3"

class VoiceSounds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}
        self.enabled = True
        self.audio_file = AUDIO_FILE

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # User joined the target VC
        if self.enabled and after.channel and after.channel.id == TARGET_CHANNEL_ID and (not before.channel or before.channel.id != after.channel.id):
            logger.info(f"{member.display_name} joined target voice channel.")

            # Prevent bot from rejoining if already connected
            if after.channel.guild.voice_client and after.channel.guild.voice_client.is_connected():
                logger.info("Bot is already connected to a voice channel.")
                return

            try:
                vc = await after.channel.connect()
                source = discord.FFmpegPCMAudio(self.audio_file)
                quieter_source = discord.PCMVolumeTransformer(source, volume=0.2)
                vc.play(quieter_source)

                while vc.is_playing():
                    await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=1))

                await vc.disconnect()
                logger.info("Played join sound and disconnected.")
            except Exception as e:
                logger.error(f"Failed to play sound in VC: {e}")

    @app_commands.command(name="togglevoicesound", description="Enable or disable voice join sounds")
    @app_commands.checks.has_permissions(administrator=True)
    async def toggle_voice_sound(self, interaction: discord.Interaction):
        self.enabled = not self.enabled
        status = "enabled" if self.enabled else "disabled"
        await interaction.response.send_message(f"Voice sound playback has been {status}.", ephemeral=True)
        logger.info(f"Voice sound playback {status} by {interaction.user.display_name}")

    @app_commands.command(name="setvoicesound", description="Set the path to the audio file for voice join")
    @app_commands.describe(file_path="Path to the new audio file")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_voice_sound(self, interaction: discord.Interaction, file_path: str):
        if not os.path.exists(file_path):
            await interaction.response.send_message("That file does not exist.", ephemeral=True)
            return
        self.audio_file = file_path
        await interaction.response.send_message(f"Voice sound updated to `{file_path}`.", ephemeral=True)
        logger.info(f"Voice sound path updated to {file_path} by {interaction.user.display_name}")

async def setup(bot):
    cog = VoiceSounds(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.toggle_voice_sound)
    bot.tree.add_command(cog.set_voice_sound)