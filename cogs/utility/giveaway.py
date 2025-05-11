import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import random
import json
import os
from datetime import datetime, timedelta

logger = logging.getLogger("S.T.E.V.E")

GIVEAWAY_DATA_FILE = "data/giveaways.json"

class GiveawayView(discord.ui.View):
    def __init__(self, message_id, save_callback):
        super().__init__(timeout=None)
        self.entries = set()
        self.message_id = message_id
        self.save_callback = save_callback

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.green, custom_id="giveaway_enter")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.entries:
            await interaction.response.send_message("You're already entered!", ephemeral=True)
        else:
            self.entries.add(interaction.user.id)
            await interaction.response.send_message("You've entered the giveaway!", ephemeral=True)
            logger.info(f"{interaction.user.display_name} entered the giveaway.")
            self.save_callback(self.message_id, self.entries)

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def parse_duration(self, duration_str: str) -> int:
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        try:
            unit = duration_str[-1]
            value = int(duration_str[:-1])
            return value * units[unit]
        except (KeyError, ValueError):
            return -1

    def save_giveaway(self, message_id, channel_id, prize, end_time, entries):
        data = {
            "message_id": message_id,
            "channel_id": channel_id,
            "prize": prize,
            "end_time": end_time.isoformat(),
            "entries": list(entries)
        }
        os.makedirs("data", exist_ok=True)
        with open(GIVEAWAY_DATA_FILE, "w") as f:
            json.dump(data, f)

    def load_giveaway(self):
        if not os.path.exists(GIVEAWAY_DATA_FILE):
            return None
        with open(GIVEAWAY_DATA_FILE, "r") as f:
            return json.load(f)

    def clear_giveaway(self):
        if os.path.exists(GIVEAWAY_DATA_FILE):
            os.remove(GIVEAWAY_DATA_FILE)

    def save_entries_callback(self, message_id, entries):
        saved = self.load_giveaway()
        if saved and saved["message_id"] == message_id:
            saved["entries"] = list(entries)
            with open(GIVEAWAY_DATA_FILE, "w") as f:
                json.dump(saved, f)

    @app_commands.command(name="giveaway", description="Start a giveaway.")
    @app_commands.describe(prize="What is being given away", duration="Duration (e.g. 10m, 1h, 2d)")
    async def giveaway(self, interaction: discord.Interaction, prize: str, duration: str):
        seconds = self.parse_duration(duration)
        if seconds <= 0:
            await interaction.response.send_message("Invalid duration format. Use something like `10m`, `1h`, or `2d`.", ephemeral=True)
            return

        view = GiveawayView(None, self.save_entries_callback)
        embed = discord.Embed(title="🎉 Giveaway!", description=f"**Prize:** ***{prize}***", color=discord.Color.purple())
        embed.set_footer(text="Click the button below to enter!")
        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        view.message_id = message.id

        logger.info(f"Giveaway started by {interaction.user.display_name} for '{prize}' lasting {duration} ({seconds}s).")

        end_time = datetime.utcnow() + timedelta(seconds=seconds)
        self.save_giveaway(message.id, interaction.channel.id, prize, end_time, view.entries)
        await asyncio.sleep(seconds)

        # Reload entries from saved file in case bot restarted
        saved = self.load_giveaway()
        if saved and saved["message_id"] == message.id:
            view.entries = set(saved.get("entries", []))

        if not view.entries:
            await message.edit(embed=discord.Embed(title="🎉 Giveaway Ended", description="No one entered. L.", color=discord.Color.red()), view=None)
            logger.info("Giveaway ended with no entries.")
        else:
            winner_id = random.choice(list(view.entries))
            winner = await interaction.guild.fetch_member(winner_id)
            await message.edit(embed=discord.Embed(title="🎉 Giveaway Winner!", description=f"Congrats {winner.mention}! You won **{prize}**!", color=discord.Color.green()), view=None)
            logger.info(f"{winner.display_name} won the giveaway for '{prize}'.")

        self.clear_giveaway()

    @commands.Cog.listener()
    async def on_ready(self):
        saved = self.load_giveaway()
        if not saved:
            return

        end_time = datetime.fromisoformat(saved["end_time"])
        remaining = (end_time - datetime.utcnow()).total_seconds()
        if remaining <= 0:
            self.clear_giveaway()
            return

        channel = self.bot.get_channel(int(saved["channel_id"]))
        if not channel:
            logger.warning("Giveaway channel not found.")
            return

        try:
            message = await channel.fetch_message(int(saved["message_id"]))
            view = GiveawayView(saved["message_id"], self.save_entries_callback)
            view.entries = set(saved.get("entries", []))
            await message.edit(view=view)
            logger.info("Restored ongoing giveaway.")

            async def complete():
                await asyncio.sleep(remaining)
                if not view.entries:
                    await message.edit(embed=discord.Embed(title="🎉 Giveaway Ended", description="No one entered. L.", color=discord.Color.red()), view=None)
                    logger.info("Restored giveaway ended with no entries.")
                else:
                    winner_id = random.choice(list(view.entries))
                    winner = await channel.guild.fetch_member(winner_id)
                    await message.edit(embed=discord.Embed(title="🎉 Giveaway Winner!", description=f"Congrats {winner.mention}! You won **{saved['prize']}**!", color=discord.Color.green()), view=None)
                    logger.info(f"{winner.display_name} won the restored giveaway for '{saved['prize']}'.")
                self.clear_giveaway()

            self.bot.loop.create_task(complete())
        except Exception as e:
            logger.error(f"Failed to restore giveaway: {e}")

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
