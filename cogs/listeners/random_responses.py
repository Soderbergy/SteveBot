import discord
from discord.ext import commands
import random
import logging

logger = logging.getLogger("S.T.E.V.E")

class RandomResponses(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.default_responses = [
            "🤖 Did someone call me?",
            "👀 I'm always watching...",
            "That was interesting. Maybe.",
            "Beep boop. Message received.",
            "I’ll pretend I didn’t see that.",
            "Wow, revolutionary insight there.",
        ]
        self.user_specific_responses = {
            615975081226534928: [  # Levii
                "Back at it again, huh?",
                "This is the guy who made me, so be nice to him!",
                "I’m not saying he’s a genius, but... well, I am."
            ],
            818929204556201985: [  # Lexi
                "Oh no, not you again 😅",
                "Why do I feel judged?",
                "Best support player NA, is that you!?"
            ],
            417024063970738179: [  # Joey
                "Don't you have aimbot allegations to deal with?",
                "Kids?!",
                "I’m not your therapist, Joey."
            ],
            640768503971840013: [  # Nathan
                "I see you, Nathan. Always lurking.",
                "What's the alcohol content of this message?",
                "On a scale of 1-20, how drunk are you right now?"
            ],
            1023401078961745962: [  # Justin
                "Make any sick silver plays lately?",
                "Not gonna lie, I’m a little scared of you.",
                "You’re like a wild card, but in a good way."
            ]
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if random.random() < 0.05:  # 5% chance
            user_id = message.author.id
            responses = self.user_specific_responses.get(user_id, self.default_responses)
            response = random.choice(responses)
            try:
                await message.channel.send(f"{message.author.mention} {response}")
                logger.info(f"Random response sent to {message.author.display_name}: {response}")
            except Exception as e:
                logger.warning(f"Failed to send random response: {e}")

async def setup(bot):
    await bot.add_cog(RandomResponses(bot))