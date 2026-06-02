from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from discord_bot_curaga.context import AppContext

REDACTED_TEXT = "--- redacted ---"


class RedactionCog(commands.Cog):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._redacted_message_ids: set[int] = set()
        self._redacting_message_ids: set[int] = set()
        self._lock = asyncio.Lock()

    @property
    def bot(self) -> commands.Bot:
        return self.ctx.bot

    @property
    def config(self):
        return self.ctx.config

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not self._should_consider_payload(payload):
            return

        if await self._is_inflight_or_redacted(payload.message_id):
            return

        message = await self._fetch_message(payload.channel_id, payload.message_id)
        if message is None:
            return

        if message.author.bot:
            return

        reaction = self._get_message_reaction(message, self.config.redaction_emoji)
        if reaction is None or reaction.count < self.config.redaction_threshold:
            return

        await self._redact_message(message)

    def _should_consider_payload(self, payload: discord.RawReactionActionEvent) -> bool:
        if not self.config.redaction_enabled:
            return False

        if self.config.redaction_threshold <= 0:
            return False

        if payload.guild_id != self.config.guild_id:
            return False

        if self.bot.user and payload.user_id == self.bot.user.id:
            return False

        if payload.message_id == self.config.message_id_rules:
            return False

        if payload.channel_id in self.config.redaction_ignore_channel_ids:
            return False

        if (
            self.config.redaction_channel_id is not None
            and payload.channel_id != self.config.redaction_channel_id
        ):
            return False

        if str(payload.emoji) != self.config.redaction_emoji:
            return False

        return True

    async def _is_inflight_or_redacted(self, message_id: int) -> bool:
        async with self._lock:
            return (
                message_id in self._redacted_message_ids
                or message_id in self._redacting_message_ids
            )

    async def _mark_redacting(self, message_id: int) -> bool:
        async with self._lock:
            if (
                message_id in self._redacted_message_ids
                or message_id in self._redacting_message_ids
            ):
                return False
            self._redacting_message_ids.add(message_id)
            return True

    async def _mark_redacted(self, message_id: int):
        async with self._lock:
            self._redacting_message_ids.discard(message_id)
            self._redacted_message_ids.add(message_id)

    async def _unmark_redacting(self, message_id: int):
        async with self._lock:
            self._redacting_message_ids.discard(message_id)

    def _get_message_reaction(self, message: discord.Message, emoji: str):
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji:
                return reaction
        return None

    async def _fetch_message(
        self, channel_id: int, message_id: int
    ) -> discord.Message | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.DiscordException as e:
                self.ctx.logger.warning(
                    f"Could not fetch channel {channel_id}: {e}",
                    extra={"skip_discord": True},
                )
                return None

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            self.ctx.logger.warning(
                f"Channel {channel_id} does not support message fetches",
                extra={"skip_discord": True},
            )
            return None

        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            return None
        except discord.Forbidden:
            self.ctx.logger.warning(
                f"Missing permissions to fetch message {message_id}",
                extra={"skip_discord": True},
            )
        except discord.HTTPException as e:
            self.ctx.logger.warning(
                f"Failed to fetch message {message_id}: {e}",
                extra={"skip_discord": True},
            )

        return None

    def _redaction_notice_text(self, message: discord.Message) -> str:
        reaction_word = (
            "reaction" if self.config.redaction_threshold == 1 else "reactions"
        )
        return (
            f"Hey {message.author.mention}, a message of yours was redacted since it received "
            f"{self.config.redaction_threshold} or more {self.config.redaction_emoji} {reaction_word}."
        )

    async def _redact_message(self, message: discord.Message):
        if not await self._mark_redacting(message.id):
            return

        try:
            if self.config.dry_run:
                self.ctx.logger.info(
                    f"Would redact message {message.id} from {message.author}"
                )
                await self._mark_redacted(message.id)
                return

            await message.delete()
            await message.channel.send(self._redaction_notice_text(message))
            self.ctx.logger.info(f"Redacted message {message.id} from {message.author}")
            await self._mark_redacted(message.id)
        except discord.Forbidden:
            self.ctx.logger.warning(
                f"Missing permissions to redact message {message.id}",
                extra={"skip_discord": True},
            )
        except discord.HTTPException as e:
            self.ctx.logger.warning(
                f"Failed to redact message {message.id}: {e}",
                extra={"skip_discord": True},
            )
        finally:
            await self._unmark_redacting(message.id)


async def setup(bot: commands.Bot, ctx: AppContext):
    await bot.add_cog(RedactionCog(ctx))
