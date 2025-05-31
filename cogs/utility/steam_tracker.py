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
                # Removed noisy summary fetch log
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
                        user_line = f"🎮 **{summary['personaname']}**"
                        if embed_key in self.active_embeds:
                            try:
                                message = await channel.fetch_message(self.active_embeds[embed_key])
                                embed = message.embeds[0]
                                if user_line not in embed.description:
                                    embed.description += f"\n{user_line}"
                                    await message.edit(embed=embed)
                            except discord.NotFound:
                                # Message was deleted or not found
                                embed = discord.Embed(title=f"{current_game} - Players", description=user_line, color=discord.Color.green())
                                message = await channel.send(embed=embed)
                                self.active_embeds[embed_key] = message.id
                        else:
                            embed = discord.Embed(title=f"{current_game} - Players", description=user_line, color=discord.Color.green())
                            message = await channel.send(embed=embed)
                            self.active_embeds[embed_key] = message.id
                    self.last_statuses[user_id] = current_game.lower()
                elif not current_game:
                    # logger.info(f"{summary['personaname']} is not currently in a tracked game.")
                    # Clear user from active embeds
                    for (channel_id, game_name), message_id in list(self.active_embeds.items()):
                        if channel_id != discord_channel_id:
                            continue
                        try:
                            channel = await self.bot.fetch_channel(channel_id)
                            message = await channel.fetch_message(message_id)
                            embed = message.embeds[0]
                            user_line = f"🎮 **{summary['personaname']}**"
                            if user_line in embed.description:
                                embed.description = embed.description.replace(f"\n{user_line}", "")
                                await message.edit(embed=embed)
                                # Remove embed if empty
                                if not embed.description.strip():
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