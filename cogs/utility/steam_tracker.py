import os
import discord
from discord.ext import commands, tasks
import json
import aiohttp
import asyncio
import logging
from discord import app_commands

logger = logging.getLogger("S.T.E.V.E")

CHECK_INTERVAL = 60  # in seconds

class SteamTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracked_users = self.load_tracked_users()
        self.last_statuses = {}
        self.channel_embeds = {}  # {channel_id: message_id}
        self.summary_cache = {}
        self.cache_timestamps = {}
        self.cache_duration = 120  # seconds
        self.check_steam_status.start()

    def cog_unload(self):
        self.check_steam_status.cancel()

    def load_tracked_users(self):
        try:
            with open("data/steam_tracking.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Couldn't load steam_tracking.json: {e}")
            return {}

    def load_channel_embeds(self):
        try:
            with open("data/steam_embed_tracking.json", "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Couldn't load steam_embed_tracking.json: {e}")
            return {}

    def save_channel_embeds(self):
        try:
            with open("data/steam_embed_tracking.json", "w") as f:
                json.dump(self.channel_embeds, f, indent=2)
        except Exception as e:
            logger.warning(f"Couldn't save steam_embed_tracking.json: {e}")

    async def fetch_player_summaries(self, steam_ids):
        steam_api_key = os.getenv("STEAM_API_KEY")
        current_time = asyncio.get_event_loop().time()

        cached = {sid: self.summary_cache[sid] for sid in steam_ids
                  if sid in self.summary_cache and (current_time - self.cache_timestamps[sid]) < self.cache_duration}
        ids_to_fetch = [sid for sid in steam_ids if sid not in cached]

        if not ids_to_fetch:
            return cached

        ids_param = ",".join(ids_to_fetch)
        url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={steam_api_key}&steamids={ids_param}"
        await asyncio.sleep(1)
        retries = 3
        backoff = 5
        for attempt in range(retries):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 429:
                        logger.warning(f"Rate limited when fetching player summaries. Retrying in {backoff} seconds...")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    data = await resp.json()
                    for player in data.get("response", {}).get("players", []):
                        sid = player["steamid"]
                        self.summary_cache[sid] = player
                        self.cache_timestamps[sid] = current_time
                    summaries = {**cached, **{p["steamid"]: p for p in data.get("response", {}).get("players", [])}}
                    return summaries
        logger.error("Failed to fetch player summaries after multiple retries.")
        return cached

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_steam_status(self):
        # Gather all unique steam IDs to batch fetch
        unique_steam_ids = list({info["steam_id"] for info in self.tracked_users.values()})
        try:
            summaries = await self.fetch_player_summaries(unique_steam_ids)
        except Exception as e:
            logger.warning(f"Error fetching player summaries: {e}")
            summaries = {}

        # Group tracked users by channel
        channel_to_users = {}
        for user_id, info in self.tracked_users.items():
            channel_id = info["channel_id"]
            channel_to_users.setdefault(channel_id, []).append((user_id, info))

        TRACKED_GAMES = ["squad", "dayz", "rainbow six siege"]

        for channel_id, users in channel_to_users.items():
            # Build embed content for the channel
            names = []
            statuses = []
            icons = []
            most_recent_game = None
            most_recent_summary = None
            most_recent_time = 0
            for user_id, info in users:
                steam_id = info["steam_id"]
                summary = summaries.get(steam_id)
                if not summary:
                    names.append(f"ID:{steam_id}")
                    statuses.append("Unknown")
                    icons.append("—")
                    continue

                personaname = summary.get("personaname", f"ID:{steam_id}")
                current_game = summary.get("gameextrainfo")
                status_text = {
                    0: "Offline",
                    1: "Online",
                    2: "Busy",
                    3: "Away",
                    4: "Snooze",
                    5: "Looking to trade",
                    6: "Looking to play"
                }.get(summary.get("personastate", 0), "Unknown")

                display_status = current_game if current_game else status_text
                names.append(personaname)
                statuses.append(display_status)

                if current_game and summary.get("gameid") and summary.get("img_icon_url"):
                    app_id = summary["gameid"]
                    icon_hash = summary["img_icon_url"]
                    icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg"
                    icons.append(f"[🖼️]({icon_url})")
                else:
                    icons.append("—")

                # Track the most recently active game for thumbnail
                if current_game and any(name in current_game.lower() for name in TRACKED_GAMES):
                    last_played = summary.get("lastlogoff", 0)
                    if last_played > most_recent_time:
                        most_recent_time = last_played
                        most_recent_game = current_game
                        most_recent_summary = summary

                last_game = self.last_statuses.get(user_id)
                current_game_lower = current_game.lower() if current_game else None
                if last_game != current_game_lower:
                    self.last_statuses[user_id] = current_game_lower

            embed = discord.Embed(title="Steam Game Tracking", color=discord.Color.green())
            embed.add_field(name="👤 Person", value="\n".join(names) or "—", inline=True)
            embed.add_field(name="🎮 Status", value="\n".join(statuses) or "—", inline=True)
            embed.add_field(name="📸 Icon", value="\n".join(icons) or "—", inline=True)
            if most_recent_summary:
                app_id = most_recent_summary.get("gameid")
                icon_hash = most_recent_summary.get("img_icon_url")
                if app_id and icon_hash:
                    icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg"
                    embed.set_thumbnail(url=icon_url)
            # Fetch or create the embed message for this channel
            message_id = self.channel_embeds.get(str(channel_id))
            channel = None
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                logger.warning(f"Channel ID {channel_id} not found.")
                continue
            except discord.Forbidden:
                logger.warning(f"No permission to access channel ID {channel_id}.")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error fetching channel {channel_id}: {e}")
                continue

            if message_id:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed)
                except discord.NotFound:
                    # Message was deleted or not found, create a new one
                    message = await channel.send(embed=embed)
                    self.channel_embeds[str(channel_id)] = message.id
                    self.save_channel_embeds()
                except discord.Forbidden:
                    logger.warning(f"No permission to edit message in channel {channel_id}.")
                except Exception as e:
                    logger.warning(f"Error editing embed message in channel {channel_id}: {e}")
            else:
                # No message exists yet, create it
                try:
                    message = await channel.send(embed=embed)
                    self.channel_embeds[str(channel_id)] = message.id
                    self.save_channel_embeds()
                except Exception as e:
                    logger.warning(f"Error sending embed message in channel {channel_id}: {e}")

    @app_commands.command(name="addsteamtrack", description="Track someone by Steam ID")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_steam_track(self, interaction: discord.Interaction, steam_id: str):
        if str(interaction.user.id) not in self.tracked_users:
            self.tracked_users[str(interaction.user.id)] = {
                "steam_id": steam_id,
                "channel_id": interaction.channel.id
            }
        else:
            self.tracked_users[str(interaction.user.id)]["steam_id"] = steam_id
            self.tracked_users[str(interaction.user.id)]["channel_id"] = interaction.channel.id
        with open("data/steam_tracking.json", "w") as f:
            json.dump(self.tracked_users, f, indent=2)
        await interaction.response.send_message(f"🛰️ Now tracking Steam activity for Steam ID `{steam_id}`.")

    @commands.Cog.listener()
    async def on_ready(self):
        self.channel_embeds = self.load_channel_embeds()
        try:
            synced = await self.bot.tree.sync()
            logger.info(f"🔧 Synced {len(synced)} app commands.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

async def setup(bot):
    await bot.add_cog(SteamTracker(bot))