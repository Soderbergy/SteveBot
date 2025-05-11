

import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from typing import Dict
import os

logger = logging.getLogger("S.T.E.V.E")

from utils.ai import generate_nicknames

class MassNickname(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.original_nicknames: Dict[int, str] = {}

    @app_commands.command(name="massnickname", description="Temporarily change everyone's nickname in a voice channel.")
    @app_commands.describe(channel="Voice channel to target", theme="Theme for nickname generation")
    async def massnickname(self, interaction: discord.Interaction, channel: discord.VoiceChannel, theme: str):
        members = [m for m in channel.members if not m.bot and m.guild_permissions.change_nickname]

        if not members:
            await interaction.response.send_message("No nicknamable members found in that channel.", ephemeral=True)
            logger.info(f"{interaction.user.display_name} tried /massnickname but no valid members found.")
            return

        await interaction.response.defer()
        logger.info(f"{interaction.user.display_name} used /massnickname in '{channel.name}' with theme '{theme}'.")

        try:
            nicknames = generate_nicknames(theme, len(members))
        except Exception as e:
            await interaction.followup.send("Failed to generate nicknames. Check the logs.")
            logger.error(f"Nickname generation failed: {e}")
            return

        for member, new_nick in zip(members, nicknames):
            try:
                self.original_nicknames[member.id] = member.nick
                await member.edit(nick=new_nick)
                logger.info(f"Changed {member.display_name} to '{new_nick}'")
            except Exception as e:
                logger.error(f"Failed to nickname {member.display_name}: {e}")

        await interaction.followup.send(f"Nicknames have been changed for 5 minutes in '{channel.name}'")

        self.bot.loop.call_later(300, self.restore_nicknames, members)

    def restore_nicknames(self, members):
        for member in members:
            original = self.original_nicknames.get(member.id)
            if original is not None:
                # Check for permissions and ownership before attempting to restore
                if (
                    not member.guild.me.guild_permissions.manage_nicknames
                    or member == member.guild.owner
                ):
                    logger.warning(
                        f"Cannot restore nickname for {member.display_name} (insufficient permissions or server owner)."
                    )
                    continue
                try:
                    self.bot.loop.create_task(member.edit(nick=original))
                    logger.info(f"Restored nickname for {member.display_name}")
                except Exception as e:
                    logger.warning(f"Failed to restore nickname for {member.display_name}: {e}")

async def setup(bot):
    await bot.add_cog(MassNickname(bot))