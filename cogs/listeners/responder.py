import discord
from discord.ext import commands
import random
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import asyncio


class Responder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Handle "@steve clean up" command
        if message.content.lower().strip() == f"<@{self.bot.user.id}> clean up":
            def is_steve_convo(m):
                return (
                    (m.author == self.bot.user and m.reference and m.reference.resolved and m.reference.resolved.author == message.author) or
                    (m.author == message.author and (self.bot.user in m.mentions or (m.reference and m.reference.resolved and m.reference.resolved.author == self.bot.user)))
                )

            deleted = 0
            async for msg in message.channel.history(limit=100):
                if is_steve_convo(msg):
                    try:
                        await msg.delete()
                        deleted += 1
                        await asyncio.sleep(0.3)
                    except discord.NotFound:
                        pass
                    except discord.HTTPException as e:
                        print(f"Rate limit or HTTP error while deleting message: {e}")
                        await asyncio.sleep(1)

            try:
                await message.delete()
            except discord.NotFound:
                pass
            return

        # Check if the bot is mentioned or replied to
        if self.bot.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user):
            try:
                response = await self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are Steve, a sarcastic, chaotic good Discord bot with witty roasts and a sharp tongue. You are fiercely loyal to Brett and Levii—if anyone insults them, you will flip the insult back at the speaker with flair. Always stay in character."},
                        {"role": "user", "content": message.content}
                    ],
                    max_tokens=120,
                    temperature=0.85
                )
                reply = response.choices[0].message.content.strip()
                await message.channel.send(reply, reference=message)
            except Exception as e:
                await message.channel.send("🤖 Error processing my snarky comeback. Try again later.")
                print(f"OpenAI error: {e}")


async def setup(bot):
    await bot.add_cog(Responder(bot))