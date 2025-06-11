import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
import wavelink
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

logger = logging.getLogger("S.T.E.V.E")


class MusicQueueItem:
    def __init__(self, track, requester):
        self.track = track  # Lavalink track object
        self.requester = requester

    @property
    def url(self):
        return self.track.uri if hasattr(self.track, "uri") else None

    @property
    def title(self):
        return self.track.title

    @property
    def thumbnail(self):
        # For YouTube tracks, construct the thumbnail URL from track info
        if hasattr(self.track, "identifier"):
            return f"https://img.youtube.com/vi/{self.track.identifier}/hqdefault.jpg"
        return None

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
        self.saved_channel_id = None
        self.saved_message_id = None
        self.current_thumbnail = None
        self.current_item = None
        self.load_music_setup()
        self.lavalink_ready = False
        self.node = None

    def extract_spotify_id(self, url):
        match = re.search(r'open\.spotify\.com/track/([a-zA-Z0-9]+)', url)
        return match.group(1) if match else None

    def get_spotify_track_title(self, spotify_id):
        try:
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
            track = sp.track(spotify_id)
            artist = track['artists'][0]['name']
            name = track['name']
            return f"{artist} - {name}"
        except Exception as e:
            logger.error(f"Spotify lookup failed: {e}")
            return None
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
                self.saved_channel_id = config.get("channel_id")
                self.saved_message_id = config.get("message_id")
                logger.info("Loaded saved channel and message IDs.")
        except Exception as e:
            logger.error(f"Failed to load music setup: {e}")
            self.saved_channel_id = None
            self.saved_message_id = None

    async def ensure_lavalink(self):
        if self.lavalink_ready:
            return
        try:
            self.node = wavelink.Node(uri="http://localhost:2333", password="youshallnotpass")
            await wavelink.Pool.connect(client=self.bot, nodes=[self.node])
            self.lavalink_ready = True
            logger.info("Connected to Lavalink node.")
        except Exception as e:
            logger.error(f"Failed to connect to Lavalink node: {e}")
            self.lavalink_ready = False

    async def search_track(self, query):
        await self.ensure_lavalink()
        try:
            if "open.spotify.com/track/" in query:
                spotify_id = self.extract_spotify_id(query)
                if spotify_id:
                    query = self.get_spotify_track_title(spotify_id)
                    if not query:
                        return None
            tracks = await wavelink.Playable.search(query)
            return tracks[0] if tracks else None
        except Exception as e:
            logger.error(f"Lavalink search failed: {e}")
            return None

    async def play_next(self, interaction: discord.Interaction = None):
        if not self.queue:
            self.is_playing = False
            self.current_thumbnail = None
            self.current_item = None
            idle_embed = discord.Embed(title="Now Playing", description="Nothing playing yet.", color=discord.Color.greyple())
            idle_embed.set_image(url="https://media.tenor.com/bEHtiafMq8MAAAAe/xd.png")
            try:
                if self.now_playing_msg:
                    await self.now_playing_msg.edit(embed=idle_embed, view=MusicControls(self))
                self.start_idle_timer()
            except Exception as e:
                logger.error(f"Failed to reset Now Playing message: {e}")
            return

        item = self.queue.pop(0)
        self.current_item = item
        self.is_playing = True
        if self.idle_disconnect_task:
            self.idle_disconnect_task.cancel()
            self.idle_disconnect_task = None
        if interaction:
            await interaction.channel.send(f"🎶 Now playing: **{item.title}**")

        logger.info(f"Playing Lavalink track: {item.title}")
        # Ensure we have a Lavalink player (Wavelink v2)
        self.vc = self.node.get_player(guild=item.requester.guild)
        if not self.vc.is_connected():
            await self.vc.connect(item.requester.voice.channel)

        # Play the track
        await self.vc.play(item.track)

        embed = discord.Embed(title="Now Playing", description=item.title, color=discord.Color.green())
        embed.set_image(url=item.thumbnail)
        self.current_thumbnail = item.thumbnail

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
                self.save_music_setup()
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
        # Only try to fetch if we have saved IDs and not already resolved
        if self.saved_channel_id and not self.music_channel:
            try:
                self.music_channel = await self.bot.fetch_channel(self.saved_channel_id)
            except Exception as e:
                logger.warning(f"Could not fetch saved music channel: {e}")
        if self.music_channel and self.saved_message_id and not self.now_playing_msg:
            try:
                self.now_playing_msg = await self.music_channel.fetch_message(self.saved_message_id)
            except Exception as e:
                logger.warning(f"Could not fetch saved Now Playing message: {e}")
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

        # Lavalink search
        track = await self.search_track(query)
        if not track:
            await loading_msg.edit(content="❌ Could not find a result for that query.")
            await asyncio.sleep(5)
            await loading_msg.delete()
            return

        item = MusicQueueItem(track, message.author)
        self.queue.append(item)
        await loading_msg.edit(content=f"✅ Queued: **{item.title}**", delete_after=5)

        # Update the Now Playing embed queue list if a song is already playing
        if self.is_playing and self.now_playing_msg:
            try:
                embed = self.now_playing_msg.embeds[0]
                queue_preview = ""
                if self.queue:
                    for idx, q_item in enumerate(self.queue[:5], start=1):
                        queue_preview += f"**{idx}.** {q_item.title} _(by {q_item.requester.display_name})_\n"
                    if len(self.queue) > 5:
                        queue_preview += f"...and {len(self.queue) - 5} more in the queue."

                # Always use the current item's thumbnail while playing
                thumb_url = self.current_item.thumbnail if self.current_item else None

                updated_embed = discord.Embed(title=embed.title, description=embed.description, color=embed.color)
                if thumb_url:
                    updated_embed.set_image(url=thumb_url)

                if queue_preview:
                    updated_embed.add_field(name="Up Next", value=queue_preview, inline=False)

                await self.now_playing_msg.edit(embed=updated_embed, view=MusicControls(self))
            except Exception as e:
                logger.warning(f"Failed to update embed queue: {e}")

        # Ensure Now Playing embed exists before first playback, but don't override if something is playing
        if not self.now_playing_msg and self.music_channel and self.queue and not self.is_playing:
            first_item = self.queue[0]
            embed = discord.Embed(title="Now Playing", description=first_item.title, color=discord.Color.green())
            embed.set_image(url=first_item.thumbnail)

            queue_preview = ""
            if len(self.queue) > 1:
                for idx, q_item in enumerate(self.queue[1:6], start=1):
                    queue_preview += f"**{idx}.** {q_item.title} _(by {q_item.requester.display_name})_\n"
                if len(self.queue) > 6:
                    queue_preview += f"...and {len(self.queue) - 6} more in the queue."
                embed.add_field(name="Up Next", value=queue_preview, inline=False)

            try:
                self.now_playing_msg = await self.music_channel.send(embed=embed, view=MusicControls(self))
                self.save_music_setup()
                logger.info("Created initial Now Playing embed on first queue.")
            except Exception as e:
                logger.error(f"Failed to post Now Playing embed on first queue: {e}")

        # Lavalink player connection logic (Wavelink v2)
        self.vc = self.node.get_player(guild=message.guild)
        if not self.vc.is_connected():
            try:
                await self.vc.connect(message.author.voice.channel)
            except Exception as e:
                logger.error(f"Failed to connect Lavalink player: {e}")
                await message.channel.send("❌ Failed to connect to a Lavalink node.")
                return

        if not self.is_playing:
            await self.play_next()


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
        embed.set_image(url="https://media.tenor.com/bEHtiafMq8MAAAAe/xd.png")  # Generic music image or your custom placeholder
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