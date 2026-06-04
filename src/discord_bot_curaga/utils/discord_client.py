from __future__ import annotations

from logging import Logger

import discord
from discord.ext import commands

from discord_bot_curaga.config import AppConfig
from discord_bot_curaga.utils.async_cache import async_cache


class DiscordClient:
    _bot: commands.Bot
    _config: AppConfig
    _logger: Logger

    def __init__(self, bot: commands.Bot, config: AppConfig, logger: Logger):
        self._bot = bot
        self._config = config
        self._logger = logger

    @async_cache
    async def get_guild(self) -> discord.Guild:
        guild = self._bot.get_guild(self._config.guild_id)
        if guild is None:
            self._logger.warning(
                f"Required guild not found: {self._config.guild_id}",
                extra={"skip_discord": True},
            )
            raise RuntimeError(f"Required guild not found: {self._config.guild_id}")

        return guild

    @async_cache
    async def get_role_for_approved(self) -> discord.Role:
        guild = await self.get_guild()
        role_id = self._config.role_id_approved
        role = guild.get_role(role_id)

        if role is None:
            self._logger.warning(
                f"Required role not found: {role_id}",
                extra={"skip_discord": True},
            )
            raise RuntimeError(f"Required role not found: {role_id}")

        return role

    @async_cache
    async def get_role_for_admin(self) -> discord.Role:
        guild = await self.get_guild()
        role_id = self._config.role_id_admin
        role = guild.get_role(role_id)

        if role is None:
            self._logger.warning(
                f"Required admin role not found: {role_id}",
                extra={"skip_discord": True},
            )
            raise RuntimeError(f"Required admin role not found: {role_id}")

        return role

    @async_cache
    async def get_channel_log(self) -> discord.abc.Messageable | None:
        channel_id = self._config.channel_id_log
        channel_log = self._bot.get_channel(channel_id)

        if channel_log is not None and isinstance(channel_log, discord.abc.Messageable):
            return channel_log

        try:
            channel_log = await self._bot.fetch_channel(channel_id)

            if not isinstance(channel_log, discord.abc.Messageable):
                self._logger.warning(
                    f"Log channel is not a messageable channel: {channel_id}",
                    extra={"skip_discord": True},
                )
                return None

            return channel_log
        except discord.NotFound:
            self._logger.warning(
                f"Optional log channel not found: {channel_id}",
                extra={"skip_discord": True},
            )
        except discord.Forbidden:
            self._logger.warning(
                f"Missing permissions to fetch log channel: {channel_id}",
                extra={"skip_discord": True},
            )
        except discord.HTTPException as e:
            self._logger.warning(
                f"Failed to fetch log channel {channel_id}: {e}",
                extra={"skip_discord": True},
            )

        return None

    @async_cache
    async def get_channel_approval(self) -> discord.abc.Messageable:
        channel_id = self._config.channel_id_approval
        channel = self._bot.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self._bot.fetch_channel(channel_id)
            except discord.NotFound as e:
                self._logger.warning(
                    f"Required approval channel not found: {channel_id}",
                    extra={"skip_discord": True},
                )
                raise RuntimeError(
                    f"Required approval channel not found: {channel_id}"
                ) from e
            except discord.Forbidden as e:
                self._logger.warning(
                    f"Missing permissions to fetch approval channel: {channel_id}",
                    extra={"skip_discord": True},
                )
                raise RuntimeError(
                    f"Required approval channel not found: {channel_id}"
                ) from e
            except discord.HTTPException as e:
                self._logger.warning(
                    f"Failed to fetch approval channel {channel_id}: {e}",
                    extra={"skip_discord": True},
                )
                raise RuntimeError(
                    f"Required approval channel not found: {channel_id}"
                ) from e

        if not isinstance(channel, discord.abc.Messageable):
            self._logger.warning(
                f"Approval channel is not a messageable channel: {channel_id}",
                extra={"skip_discord": True},
            )
            raise RuntimeError(f"Required approval channel not found: {channel_id}")

        return channel

    @async_cache
    async def get_channel_rules(self) -> discord.TextChannel | discord.Thread:
        channel_id = self._config.channel_id_rules
        channel = self._bot.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self._bot.fetch_channel(channel_id)
            except discord.NotFound as e:
                self._logger.warning(
                    f"Required rules channel not found: {channel_id}",
                    extra={"skip_discord": True},
                )
                raise RuntimeError(
                    f"Required rules channel not found: {channel_id}"
                ) from e
            except discord.Forbidden as e:
                self._logger.warning(
                    f"Missing permissions to fetch rules channel: {channel_id}",
                    extra={"skip_discord": True},
                )
                raise RuntimeError(
                    f"Required rules channel not found: {channel_id}"
                ) from e
            except discord.HTTPException as e:
                self._logger.warning(
                    f"Failed to fetch rules channel {channel_id}: {e}",
                    extra={"skip_discord": True},
                )
                raise RuntimeError(
                    f"Required rules channel not found: {channel_id}"
                ) from e

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            self._logger.warning(
                f"Rules channel does not support message purge/send: {channel_id}",
                extra={"skip_discord": True},
            )
            raise RuntimeError(f"Required rules channel not found: {channel_id}")

        return channel

    async def fetch_message(
        self, channel_id: int, message_id: int
    ) -> discord.Message | None:
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self._bot.fetch_channel(channel_id)
            except discord.DiscordException as e:
                self._logger.warning(
                    f"Could not fetch channel {channel_id}: {e}",
                    extra={"skip_discord": True},
                )
                return None

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            self._logger.warning(
                f"Channel {channel_id} does not support message fetches",
                extra={"skip_discord": True},
            )
            return None

        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            self._logger.warning(
                f"Could not find message {message_id} in channel {channel_id}",
                extra={"skip_discord": True},
            )
        except discord.Forbidden:
            self._logger.warning(
                f"Missing permissions to fetch message {message_id} in channel {channel_id}",
                extra={"skip_discord": True},
            )
        except discord.HTTPException as e:
            self._logger.warning(
                f"Failed to fetch message {message_id} in channel {channel_id}: {e}",
                extra={"skip_discord": True},
            )

        return None

    async def get_guild_member(self, user_id: int) -> discord.Member | None:
        guild = await self.get_guild()

        member = guild.get_member(user_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(user_id)
        except discord.NotFound:
            self._logger.warning(
                f"Could not find member with id {user_id}",
                extra={"skip_discord": True},
            )
        except discord.Forbidden:
            self._logger.warning(
                f"Missing permissions to fetch member with id {user_id}",
                extra={"skip_discord": True},
            )
        except discord.HTTPException as e:
            self._logger.warning(
                f"Failed to fetch member with id {user_id}: {e}",
                extra={"skip_discord": True},
            )

        return None
