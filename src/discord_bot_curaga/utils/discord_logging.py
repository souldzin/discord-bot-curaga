import asyncio
import logging

from .discord_client import DiscordClient


class DiscordLogHandler(logging.Handler):
    _client: DiscordClient

    def __init__(self, client: DiscordClient):
        super().__init__()
        self._client = client

    def _should_skip(self, record):
        return getattr(record, "skip_discord", False)

    def emit(self, record):
        if self._should_skip(record):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(self._log_to_channel(record))

    async def _log_to_channel(self, record):
        channel = await self._client.get_channel_log()
        if channel:
            message = self.format(record)
            await channel.send(message)
