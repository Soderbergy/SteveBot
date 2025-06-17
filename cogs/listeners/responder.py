import discord
from discord.ext import commands
import random
import openai
import os
from dotenv import load_dotenv


class Responder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        openai.api_key = os.getenv("OPENAI_API_KEY")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Check if the bot is mentioned or replied to
        if self.bot.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == self.bot.user):
            handled = False  # Flag to prevent duplicate AI replies

            # Check for mute command
            if "mute" in message.content.lower() and message.mentions:
                for member in message.mentions:
                    if member == self.bot.user:
                        await message.channel.send("Nice try. I’m too powerful to be controlled like that. 😎")
                        continue
                    if member != self.bot.user and isinstance(member, discord.Member):
                        if member.voice and not member.voice.mute:
                            try:
                                await member.edit(mute=True)
                                await message.channel.send(f"Muted {member.display_name}. Sweet dreams. 😌")
                            except discord.Forbidden:
                                await message.channel.send("I don’t have permission to mute them. Lame.")
                            except Exception as e:
                                await message.channel.send("Tried to mute them but something went kaboom.")
                                print(f"Error muting user: {e}")
                        else:
                            await message.channel.send(f"{member.display_name} isn’t even talking. What do you want me to do, telepathically mute them?")
                handled = True

            # Check for disconnect command
            elif "disconnect" in message.content.lower() and message.mentions:
                for member in message.mentions:
                    if member == self.bot.user:
                        await message.channel.send("Nice try. I’m too powerful to be controlled like that. 😎")
                        continue
                    if member != self.bot.user and isinstance(member, discord.Member):
                        if member.voice:
                            try:
                                await member.edit(voice_channel=None)
                                await message.channel.send(f"{member.display_name} has been yeeted from the voice channel. 🪂")
                            except discord.Forbidden:
                                await message.channel.send("Can't disconnect them. I lack the authority. 😤")
                            except Exception as e:
                                await message.channel.send("Error during disconnect. The wires are fried.")
                                print(f"Error disconnecting user: {e}")
                        else:
                            await message.channel.send(f"{member.display_name} isn’t even in a voice channel. What am I disconnecting, their soul?")
                handled = True

            # Check for deafen command
            elif "deafen" in message.content.lower() and message.mentions:
                for member in message.mentions:
                    if member == self.bot.user:
                        await message.channel.send("Nice try. I’m too powerful to be controlled like that. 😎")
                        continue
                    if member != self.bot.user and isinstance(member, discord.Member):
                        if member.voice and not member.voice.deaf:
                            try:
                                await member.edit(deafen=True)
                                await message.channel.send(f"{member.display_name} can’t hear a thing now. Silence is golden. 🤫")
                            except discord.Forbidden:
                                await message.channel.send("I tried to deafen them but the law says no.")
                            except Exception as e:
                                await message.channel.send("Error deafening. My ears are ringing just thinking about it.")
                                print(f"Error deafening user: {e}")
                        else:
                            await message.channel.send(f"{member.display_name} is already deafened or not in voice.")
                handled = True

            # Check for move command (example: move to bot's voice channel)
            elif "move" in message.content.lower() and message.mentions:
                if message.author.voice:
                    target_channel = message.author.voice.channel
                    for member in message.mentions:
                        if member == self.bot.user:
                            await message.channel.send("Nice try. I’m too powerful to be controlled like that. 😎")
                            continue
                        if member != self.bot.user and isinstance(member, discord.Member):
                            if member.voice:
                                try:
                                    await member.edit(voice_channel=target_channel)
                                    await message.channel.send(f"{member.display_name} has been summoned to your domain. 🧙‍♂️")
                                except discord.Forbidden:
                                    await message.channel.send("No can do. Voice channel sorcery denied.")
                                except Exception as e:
                                    await message.channel.send("Couldn’t move them. They resisted.")
                                    print(f"Error moving user: {e}")
                            else:
                                await message.channel.send(f"{member.display_name} isn’t in a voice channel. What am I supposed to move, thin air?")
                else:
                    await message.channel.send("You're not in a voice channel. How do I know where to teleport them?")
                handled = True

            if not handled:
                try:
                    prompt = f"You are Steve, a sarcastic, slightly unhinged but loyal Discord bot. You roast users with chaotic charm, drop clever comebacks, and provide helpful answers when needed—like if Deadpool coded Clippy. Stay in-character and witty.\nUser: \"{message.content}\""
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "You are Steve, a sarcastic, chaotic good Discord bot with witty roasts and a sharp tongue. Always stay in character."},
                            {"role": "user", "content": message.content}
                        ],
                        max_tokens=120,
                        temperature=0.85
                    )
                    reply = response.choices[0].message["content"].strip()
                    await message.channel.send(reply)
                except Exception as e:
                    await message.channel.send("🤖 Error processing my snarky comeback. Try again later.")
                    print(f"OpenAI error: {e}")


async def setup(bot):
    await bot.add_cog(Responder(bot))