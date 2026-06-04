from discord import app_commands
import discord
from discord.ext import commands


class PingCog(commands.Cog):
    @app_commands.command(
        name="ping",
        description="Ping pong.",
    )
    @app_commands.guild_only()
    async def curaga_rules_sync(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PingCog())
