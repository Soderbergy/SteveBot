import discord
from discord.ext import commands
import json
import os
import logging
logger = logging.getLogger("S.T.E.V.E")
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = "data/atk_def_data.json"
CHANNEL_ID = int(os.getenv("SCOREBOARD_CHANNEL_ID"))

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"attack": 0, "defend": 0}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

class AtkDefView(discord.ui.View):
    def __init__(self, data):
        super().__init__(timeout=None)
        self.data = data

    @discord.ui.button(label="Attack +1", style=discord.ButtonStyle.red, custom_id="attack_button")
    async def increment_attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.data["attack"] += 1
        save_data(self.data)
        logger.info(f"{interaction.user.display_name} incremented attack to {self.data['attack']}")
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Defend +1", style=discord.ButtonStyle.blurple, custom_id="defend_button")
    async def increment_defend(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.data["defend"] += 1
        save_data(self.data)
        logger.info(f"{interaction.user.display_name} incremented defend to {self.data['defend']}")
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    def make_embed(self):
        embed = discord.Embed(title="Siege A/D Tracker", color=discord.Color.gold())
        embed.add_field(name="Attacks First", value=str(self.data["attack"]), inline=True)
        embed.add_field(name="Defends First", value=str(self.data["defend"]), inline=True)
        return embed

class AtkDefTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()

    @commands.Cog.listener()
    async def on_ready(self):
        channel = self.bot.get_channel(CHANNEL_ID)
        if channel is None:
            logger.error("Could not find the scoreboard channel.")
            return

        view = AtkDefView(self.data)
        embed = view.make_embed()

        try:
            message_id = self.data.get("message_id")
            if message_id:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed, view=view)
                logger.info("Scoreboard updated.")
            else:
                msg = await channel.send(embed=embed, view=view)
                self.data["message_id"] = msg.id
                save_data(self.data)
                logger.info("Scoreboard message posted.")
        except Exception as e:
            logger.error(f"Failed to fetch/edit scoreboard: {e}")

async def setup(bot):
    bot.add_view(AtkDefView(load_data()))
    await bot.add_cog(AtkDefTracker(bot))
