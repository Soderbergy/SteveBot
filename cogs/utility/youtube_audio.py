import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import yt_dlp
import logging
import os
import json
from datetime import datetime, timedelta

logger = logging.getLogger("S.T.E.V.E")

COOKIE_WARNING_THRESHOLD = timedelta(days=3)

class MusicQueueItem:
    def __init__(self, url, title, thumbnail, requester, stream_url):
        self.url = url
        self.title = title
        self.thumbnail = thumbnail
        self.requester = requester
        self.stream_url = stream_url

class MusicControls(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.player.vc and self.player.vc.is_playing():
            self.player.vc.stop()
            await interaction.response.send_message("⏭️ Skipping...", ephemeral=True)

    @discord.ui.button(label="⏯️ Play/Pause", style=discord.ButtonStyle.grey)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.vc:
            await interaction.response.send_message("Bot is not connected to a voice channel.", ephemeral=True)
            return

        if self.player.vc.is_playing():
            self.player.vc.pause()
            await interaction.response.send_message("⏸️ Paused", ephemeral=True)
        elif self.player.vc.is_paused():
            self.player.vc.resume()
            await interaction.response.send_message("▶️ Resumed", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)

from discord import File

class YouTubeAudio(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.vc = None
        self.now_playing_msg = None
        self.is_playing = False
        self.music_channel = None
        self.idle_disconnect_task = None
        self.load_music_setup()
    def save_music_setup(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open("data/music_config.json", "w") as f:
                json.dump({
                    "channel_id": self.music_channel.id if self.music_channel else None,
                    "message_id": self.now_playing_msg.id if self.now_playing_msg else None
                }, f)
            logger.info("Saved music channel and message ID.")
        except Exception as e:
            logger.error(f"Failed to save music setup: {e}")

    def load_music_setup(self):
        try:
            config_path = "data/music_config.json"
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                channel_id = config.get("channel_id")
                message_id = config.get("message_id")
                if channel_id:
                    self.music_channel = self.bot.get_channel(channel_id)
                if self.music_channel and message_id:
                    # fetch_message must be awaited, but __init__ is not async; use asyncio.run_coroutine_threadsafe
                    try:
                        self.now_playing_msg = asyncio.run_coroutine_threadsafe(
                            self.music_channel.fetch_message(message_id),
                            self.bot.loop
                        ).result()
                    except Exception as e:
                        logger.warning(f"Could not fetch saved Now Playing message: {e}")
                logger.info("Loaded music channel and message ID.")
        except Exception as e:
            logger.error(f"Failed to load music setup: {e}")

    @tasks.loop(hours=6)
    async def check_cookie_freshness(self):
        try:
            cookie_path = "assets/cookies.txt"
            if not os.path.exists(cookie_path):
                logger.warning("❌ Cookie check failed: cookies.txt not found.")
                return
            last_modified = datetime.fromtimestamp(os.path.getmtime(cookie_path))
            age = datetime.now() - last_modified
            if age > COOKIE_WARNING_THRESHOLD:
                warning_msg = f"⚠️ The cookies.txt file is {age.days} days old and may soon expire. Please refresh it with /uploadcookies."
                logger.warning(warning_msg)
                if self.music_channel:
                    await self.music_channel.send(warning_msg)
        except Exception as e:
            logger.error(f"Error checking cookie freshness: {e}")

    def search_youtube(self, query):
        with yt_dlp.YoutubeDL({
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'cookiefile': 'assets/cookies.txt'
        }) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
                return MusicQueueItem(
                    url=info['id'],
                    title=info['title'],
                    thumbnail=info['thumbnail'],
                    requester=None,
                    stream_url=info['url']
                )
            except Exception as e:
                logger.error(f"YouTube search failed: {e}")
                return None

    async def play_next(self, interaction: discord.Interaction = None):
        if not self.queue:
            self.is_playing = False
            idle_embed = discord.Embed(title="Now Playing", description="Nothing playing yet.", color=discord.Color.greyple())
            idle_embed.set_image(url="https://i.imgur.com/ZwBtM6K.png")
            try:
                if self.now_playing_msg:
                    await self.now_playing_msg.edit(embed=idle_embed, view=MusicControls(self))
                self.start_idle_timer()
            except Exception as e:
                logger.error(f"Failed to reset Now Playing message: {e}")
            return

        item = self.queue.pop(0)
        self.is_playing = True
        if self.idle_disconnect_task:
            self.idle_disconnect_task.cancel()
            self.idle_disconnect_task = None
        if interaction:
            await interaction.channel.send(f"🎶 Now playing: **{item.title}**")

        logger.info(f"Streaming from URL: {item.stream_url}")
        source = discord.FFmpegPCMAudio(item.stream_url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn")
        self.vc.play(source, after=lambda e: self.bot.loop.create_task(self.play_next()))

        embed = discord.Embed(title="Now Playing", description=item.title, color=discord.Color.green())
        embed.set_image(url=item.thumbnail)

        # Format updated upcoming queue
        queue_preview = ""
        if self.queue:
            for idx, q_item in enumerate(self.queue[:5], start=1):
                queue_preview += f"**{idx}.** {q_item.title} _(by {q_item.requester.display_name})_\n"
            if len(self.queue) > 5:
                queue_preview += f"...and {len(self.queue) - 5} more in the queue."
            embed.add_field(name="Up Next", value=queue_preview, inline=False)

        try:
            if self.now_playing_msg:
                await self.now_playing_msg.edit(embed=embed, view=MusicControls(self))
            else:
                self.now_playing_msg = await self.music_channel.send(embed=embed, view=MusicControls(self))
                self.save_music_setup()  # Save message ID if created here
        except Exception as e:
            logger.error(f"Failed to update Now Playing message: {e}")

    def start_idle_timer(self):
        if self.idle_disconnect_task:
            self.idle_disconnect_task.cancel()
        self.idle_disconnect_task = self.bot.loop.create_task(self.disconnect_after_idle())

    async def disconnect_after_idle(self):
        await asyncio.sleep(600)
        if self.vc and self.vc.is_connected() and not self.is_playing:
            await self.vc.disconnect()
            logger.info("SteveBot disconnected due to inactivity.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.music_channel:
            self.load_music_setup()
        self.check_cookie_freshness.start()
        logger.info("YouTubeAudio cog ready.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.music_channel or message.channel.id != self.music_channel.id or message.author.bot:
            return

        query = message.content.strip()
        # Delete user message right away
        try:
            await message.delete()
        except Exception:
            pass

        loading_msg = await message.channel.send(f"🔍 Searching YouTube for: `{query}`...")

        if not message.author.voice or not message.author.voice.channel:
            await loading_msg.edit(content=f"{message.author.mention} you must be in a voice channel to queue music.")
            await asyncio.sleep(5)
            await loading_msg.delete()
            return

        item = self.search_youtube(query)
        if not item:
            await loading_msg.edit(content="❌ Could not find a result for that query.")
            await asyncio.sleep(5)
            await loading_msg.delete()
            return

        item.requester = message.author
        self.queue.append(item)
        await loading_msg.edit(content=f"✅ Queued: **{item.title}**")

        if not self.vc or not self.vc.is_connected():
            self.vc = await message.author.voice.channel.connect()

        if not self.is_playing:
            await self.play_next()

    @app_commands.command(name="uploadcookies", description="Upload a new cookies.txt file for YouTube access.")
    @app_commands.checks.has_permissions(administrator=True)
    async def upload_cookies(self, interaction: discord.Interaction, attachment: discord.Attachment):
        if not attachment.filename.endswith(".txt"):
            await interaction.response.send_message("❌ Please upload a valid cookies.txt file.", ephemeral=True)
            return

        try:
            file_bytes = await attachment.read()
            with open("assets/cookies.txt", "wb") as f:
                f.write(file_bytes)
            await interaction.response.send_message("✅ Cookies file updated successfully.", ephemeral=True)
            logger.info(f"Cookies file updated by {interaction.user.display_name}")
        except Exception as e:
            logger.error(f"Failed to save cookies file: {e}")
            await interaction.response.send_message("❌ Failed to update cookies file.", ephemeral=True)

    @app_commands.command(name="setupmusic", description="Setup the music channel automatically.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_music_channel(self, interaction: discord.Interaction):
        guild = interaction.guild
        existing = discord.utils.get(guild.text_channels, name="steve-music")

        if existing:
            self.music_channel = existing
            await interaction.response.send_message(f"🎶 Music channel already exists: {existing.mention}", ephemeral=True)
        else:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
                guild.me: discord.PermissionOverwrite(send_messages=True, manage_messages=True)
            }
            new_channel = await guild.create_text_channel("steve-music", overwrites=overwrites)
            self.music_channel = new_channel
            await interaction.response.send_message(f"✅ Created music channel: {new_channel.mention}", ephemeral=True)
            logger.info(f"Music channel created: {new_channel.name}")

        # Post a placeholder "Now Playing" embed with controls
        embed = discord.Embed(title="Now Playing", description="Nothing playing yet.", color=discord.Color.greyple())
        embed.set_image(url="https://i.imgur.com/ZwBtM6K.png")  # Generic music image or your custom placeholder
        try:
            if not self.now_playing_msg:
                self.now_playing_msg = await self.music_channel.send(embed=embed, view=MusicControls(self))
                self.save_music_setup()
                logger.info("Posted initial Now Playing embed.")
            else:
                await self.now_playing_msg.edit(embed=embed, view=MusicControls(self))
                logger.info("Updated existing Now Playing embed.")
        except Exception as e:
            logger.error(f"Failed to post/update Now Playing embed: {e}")

async def setup(bot):
    cog = YouTubeAudio(bot)
    await bot.add_cog(cog)
    # Ensure manual command registration for app commands if needed
    try:
        bot.tree.add_command(cog.show_queue)
    except Exception:
        pass