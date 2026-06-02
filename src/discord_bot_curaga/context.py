from dataclasses import dataclass
from logging import Logger

from discord.ext import commands

from .utils.discord_client import DiscordClient
from .config import AppConfig


@dataclass
class AppContext:
    config: AppConfig
    logger: Logger
    client: DiscordClient
    bot: commands.Bot
