import logging
import sys

from dotenv import load_dotenv
import discord
from discord.ext import commands

from discord_bot_curaga.utils.discord_client import DiscordClient
from discord_bot_curaga.utils.discord_logging import DiscordLogHandler

from .config import AppConfig
from .context import AppContext


class CuragaBot(commands.Bot):
    _ctx: AppContext | None

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.reactions = True

        super().__init__(command_prefix="!", intents=intents)
        self._ctx = None

    def setup_context(self, ctx: AppContext):
        self._ctx = ctx

    async def setup_hook(self):
        if self._ctx is None:
            raise RuntimeError("Must call setup_context first!")

        from discord_bot_curaga.cogs import heartbeat, onboarding

        await onboarding.setup(self, self._ctx)
        await heartbeat.setup(self, self._ctx)


def setup_logging(logger: logging.Logger, ctx: AppContext):
    logger.setLevel(logging.INFO)

    # Step: Create handlers
    log_handler_stdout = logging.StreamHandler(sys.stdout)
    log_handler_discord = DiscordLogHandler(client=ctx.client)
    log_handler_discord.level = logging.INFO

    # Step: Setup formatters
    log_prefix = "[DRY RUN] " if ctx.config.dry_run else ""
    log_handler_stdout.setFormatter(
        logging.Formatter(f"{log_prefix}%(asctime)s [%(levelname)s] %(message)s")
    )
    log_handler_discord.setFormatter(logging.Formatter(f"{log_prefix} %(message)s"))

    # Step: Add handlers
    logger.addHandler(log_handler_discord)
    logger.addHandler(log_handler_stdout)


def main():
    load_dotenv()
    config = AppConfig.create_from_env()
    logger = logging.getLogger("app")
    bot = CuragaBot()
    context = AppContext(
        config=config,
        logger=logger,
        client=DiscordClient(bot=bot, config=config, logger=logger),
    )

    setup_logging(logger, context)

    bot.setup_context(context)
    bot.run(config.token)


if __name__ == "__main__":
    main()
