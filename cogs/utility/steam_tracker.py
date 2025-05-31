import os
import discord
from discord.ext import commands, tasks
import json
import aiohttp
import asyncio
import logging

logger = logging.getLogger("S.T.E.V.E")

CHECK_INTERVAL = 60  # in seconds

class SteamTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracked_users = self.load_tracked_users()
        self.last_statuses = {}
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

    async def fetch_player_summary(self, steam_id):
        steam_api_key = os.getenv("STEAM_API_KEY")
        url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={steam_api_key}&steamids={steam_id}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return data.get("response", {}).get("players", [])[0]

    @tasks.loop(seconds=CHECK_INTERVAL)
    async def check_steam_status(self):
        for user_id, info in self.tracked_users.items():
            steam_id = info["steam_id"]
            discord_channel_id = info["channel_id"]
            last_game = self.last_statuses.get(user_id, None)

            try:
                summary = await self.fetch_player_summary(steam_id)
                logger.info(f"Fetched summary for {steam_id}: {summary}")
                current_game = summary.get("gameextrainfo")

                TRACKED_GAMES = ["squad", "dayz", "rainbow six siege"]

                if current_game and any(name in current_game.lower() for name in TRACKED_GAMES) and last_game != current_game.lower():
                    logger.info(f"Match found for {summary['personaname']} playing {current_game}")
                    # Post notification
                    channel = self.bot.get_channel(discord_channel_id)
                    if not channel:
                        logger.warning(f"Could not find Discord channel with ID {discord_channel_id}.")
                    if channel:
                        logger.info(f"Sending message to channel {channel.id} about {summary['personaname']} launching {current_game}")
                        await channel.send(f"🎮 **{summary['personaname']}** just launched **{current_game}**!")
                    self.last_statuses[user_id] = current_game.lower()
                elif not current_game:
                    logger.info(f"{summary['personaname']} is not currently in a tracked game.")
                    self.last_statuses[user_id] = None

            except Exception as e:
                logger.warning(f"Error checking Steam status for {steam_id}: {e}")

    from discord import app_commands

    @app_commands.command(name="addsteamtrack", description="Track someone by Steam ID")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_steam_track(self, interaction: discord.Interaction, steam_id: str):
        self.tracked_users[str(interaction.user.id)] = {
            "steam_id": steam_id,
            "channel_id": interaction.channel.id
        }
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