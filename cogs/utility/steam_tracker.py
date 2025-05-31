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
        self.active_embeds = {}  # {(channel_id, game_name): message_id}
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
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                for player in data.get("response", {}).get("players", []):
                    sid = player["steamid"]
                    self.summary_cache[sid] = player
                    self.cache_timestamps[sid] = current_time
                summaries = {**cached, **{p["steamid"]: p for p in data.get("response", {}).get("players", [])}}
                return summaries

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_steam_status(self):
        # Gather all unique steam IDs to batch fetch
        unique_steam_ids = list({info["steam_id"] for info in self.tracked_users.values()})
        try:
            summaries = await self.fetch_player_summaries(unique_steam_ids)
        except Exception as e:
            logger.warning(f"Error fetching player summaries: {e}")
            summaries = {}

        for user_id, info in self.tracked_users.items():
            steam_id = info["steam_id"]
            discord_channel_id = info["channel_id"]
            last_game = self.last_statuses.get(user_id, None)

            try:
                summary = summaries.get(steam_id)
                if not summary:
                    continue
                current_game = summary.get("gameextrainfo")

                TRACKED_GAMES = ["squad", "dayz", "rainbow six siege"]

                if current_game and any(name in current_game.lower() for name in TRACKED_GAMES) and last_game != current_game.lower():
                    logger.info(f"Match found for {summary.get('personaname', 'Unknown User')} playing {current_game}")
                    # Post notification
                    try:
                        channel = await self.bot.fetch_channel(discord_channel_id)
                    except discord.NotFound:
                        logger.warning(f"Channel ID {discord_channel_id} not found (NotFound).")
                        channel = None
                    except discord.Forbidden:
                        logger.warning(f"No permission to access channel ID {discord_channel_id}.")
                        channel = None
                    except Exception as e:
                        logger.warning(f"Unexpected error fetching channel {discord_channel_id}: {e}")
                        channel = None
                    embed_key = (discord_channel_id, current_game.lower())
                    if channel:
                        # Build the tracked players list (all tracked for this channel)
                        tracked_names = []
                        for uid, inf in self.tracked_users.items():
                            if inf["channel_id"] == discord_channel_id:
                                s = summaries.get(inf["steam_id"])
                                if s:
                                    tracked_names.append(s.get("personaname", f"ID:{inf['steam_id']}"))
                                else:
                                    tracked_names.append(f"ID:{inf['steam_id']}")
                        # Build the currently playing list for this game in this channel
                        currently_playing = []
                        for uid, inf in self.tracked_users.items():
                            if inf["channel_id"] == discord_channel_id:
                                s = summaries.get(inf["steam_id"])
                                if s:
                                    cg = s.get("gameextrainfo")
                                    if cg and cg.lower() == current_game.lower():
                                        currently_playing.append(f"{s.get('personaname', f'ID:{inf['steam_id']}')} — {cg}")
                        user_line = "\n".join(currently_playing) if currently_playing else "No one currently playing."
                        if embed_key in self.active_embeds:
                            try:
                                message = await channel.fetch_message(self.active_embeds[embed_key])
                                embed = message.embeds[0]
                                # Rebuild both fields
                                embed.clear_fields()
                                embed.title = f"{current_game} - Tracking"
                                embed.add_field(name="Tracked Players", value="\n".join(tracked_names) if tracked_names else "None", inline=False)
                                embed.add_field(name="Currently Playing", value=user_line, inline=False)
                                await message.edit(embed=embed)
                            except discord.NotFound:
                                # Message was deleted or not found
                                embed = discord.Embed(title=f"{current_game} - Tracking", color=discord.Color.green())
                                app_id = summary.get("gameid")
                                icon_hash = summary.get("img_icon_url")
                                if app_id and icon_hash:
                                    icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg"
                                    embed.set_thumbnail(url=icon_url)
                                embed.add_field(name="Tracked Players", value="\n".join(tracked_names) if tracked_names else "None", inline=False)
                                embed.add_field(name="Currently Playing", value=user_line, inline=False)
                                message = await channel.send(embed=embed)
                                self.active_embeds[embed_key] = message.id
                        else:
                            embed = discord.Embed(title=f"{current_game} - Tracking", color=discord.Color.green())
                            app_id = summary.get("gameid")
                            icon_hash = summary.get("img_icon_url")
                            if app_id and icon_hash:
                                icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg"
                                embed.set_thumbnail(url=icon_url)
                            embed.add_field(name="Tracked Players", value="\n".join(tracked_names) if tracked_names else "None", inline=False)
                            embed.add_field(name="Currently Playing", value=user_line, inline=False)
                            message = await channel.send(embed=embed)
                            self.active_embeds[embed_key] = message.id
                    self.last_statuses[user_id] = current_game.lower()
                elif not current_game:
                    # Remove user from "Currently Playing" field of all relevant embeds
                    for (channel_id, game_name), message_id in list(self.active_embeds.items()):
                        if channel_id != discord_channel_id:
                            continue
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                            message = await channel.fetch_message(message_id)
                            embed = message.embeds[0]
                            # Rebuild the currently playing list for this game in this channel
                            currently_playing = []
                            for uid, inf in self.tracked_users.items():
                                if inf["channel_id"] == channel_id:
                                    s = summaries.get(inf["steam_id"])
                                    if s:
                                        cg = s.get("gameextrainfo")
                                        if cg and cg.lower() == game_name:
                                            currently_playing.append(f"{s.get('personaname', f'ID:{inf['steam_id']}')} — {cg}")
                            user_line = "\n".join(currently_playing) if currently_playing else "No one currently playing."
                            # Also rebuild tracked players field
                            tracked_names = []
                            for uid, inf in self.tracked_users.items():
                                if inf["channel_id"] == channel_id:
                                    s = summaries.get(inf["steam_id"])
                                    if s:
                                        tracked_names.append(s.get("personaname", f"ID:{inf['steam_id']}"))
                                    else:
                                        tracked_names.append(f"ID:{inf['steam_id']}")
                            embed.clear_fields()
                            embed.title = f"{current_game} - Tracking"
                            app_id = summary.get("gameid")
                            icon_hash = summary.get("img_icon_url")
                            if app_id and icon_hash:
                                icon_url = f"https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps/{app_id}/{icon_hash}.jpg"
                                embed.set_thumbnail(url=icon_url)
                            embed.add_field(name="Tracked Players", value="\n".join(tracked_names) if tracked_names else "None", inline=False)
                            embed.add_field(name="Currently Playing", value=user_line, inline=False)
                            await message.edit(embed=embed)
                            # Remove embed if no one is playing this game anymore
                            if not currently_playing:
                                await message.delete()
                                del self.active_embeds[(channel_id, game_name)]
                        except Exception as e:
                            logger.warning(f"Error clearing embed for {summary['personaname']} in {game_name}: {e}")
                    self.last_statuses[user_id] = None

            except Exception as e:
                logger.warning(f"Error checking Steam status for {steam_id}: {e}")

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
        try:
            synced = await self.bot.tree.sync()
            logger.info(f"🔧 Synced {len(synced)} app commands.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

async def setup(bot):
    await bot.add_cog(SteamTracker(bot))