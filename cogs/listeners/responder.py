import discord
from discord.ext import commands
import random
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv


class Responder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if the bot is mentioned or replied to
        if self.bot.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user):
            if message.author.id == 615975081226534928 and random.random() < 0.3:
                await message.channel.send(random.choice([
                    "Yes Levii, I'm always here for emotional damage delivery. 💥",
                    "Say the word, and I'll roast them into ash.",
                    "Oh hey boss! Got another soul to smite?",
                ]))
                return
            try:
                prompt = f"You are Steve, a sarcastic, slightly unhinged but loyal Discord bot. You roast users with chaotic charm, drop clever comebacks, and provide helpful answers when needed—like if Deadpool coded Clippy. Stay in-character and witty.\nUser: \"{message.content}\""
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are Steve, a sarcastic, chaotic good Discord bot with witty roasts and a sharp tongue. Always stay in character."},
                        {"role": "user", "content": message.content}
                    ],
                    max_tokens=120,
                    temperature=0.85
                )
                reply = response.choices[0].message.content.strip()
                await message.channel.send(reply)
            except Exception as e:
                await message.channel.send("🤖 Error processing my snarky comeback. Try again later.")
                print(f"OpenAI error: {e}")


async def setup(bot):
    await bot.add_cog(Responder(bot))