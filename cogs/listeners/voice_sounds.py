import discord
from discord.ext import commands
import os
import logging

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

    @commands.command(name="togglevoicesound")
    @commands.has_permissions(administrator=True)
    async def toggle_voice_sound(self, ctx):
        self.enabled = not self.enabled
        status = "enabled" if self.enabled else "disabled"
        await ctx.send(f"Voice sound playback has been {status}.")
        logger.info(f"Voice sound playback {status} by {ctx.author.display_name}")

    @commands.command(name="setvoicesound")
    @commands.has_permissions(administrator=True)
    async def set_voice_sound(self, ctx, *, file_path: str):
        if not os.path.exists(file_path):
            await ctx.send("That file does not exist.")
            return
        self.audio_file = file_path
        await ctx.send(f"Voice sound updated to `{file_path}`.")
        logger.info(f"Voice sound path updated to {file_path} by {ctx.author.display_name}")

async def setup(bot):
    await bot.add_cog(VoiceSounds(bot))