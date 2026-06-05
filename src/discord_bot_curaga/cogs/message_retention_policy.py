from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import discord
from discord import TextChannel, Thread, app_commands
from discord.ext import commands, tasks

from discord_bot_curaga.context import AppContext
from discord_bot_curaga.utils.discord_types import ChannelWithDeleteMessages
from discord_bot_curaga.utils.iter import chunked
from discord_bot_curaga.utils.time import get_every_hour
from discord_bot_curaga.views.retention_confirmation import (
    RetentionConfirmationView,
)

BULK_DELETE_MAX_AGE = timedelta(days=14)
BULK_DELETE_CHUNK_SIZE = 100


@dataclass
class ChannelPurgeSummary:
    channel_label: str
    candidates: int
    pinned_skipped: int
    delete_candidates: int
    has_old_candidates: bool
    deleted: int = 0
    failures: int = 0


@dataclass
class PurgeSummary:
    channels_checked: int = 0
    channels_with_candidates: int = 0
    deleted: int = 0
    pinned_skipped: int = 0
    channels_with_old_candidates: int = 0
    failures: int = 0
    per_channel: list[ChannelPurgeSummary] = field(default_factory=list)


class MessageRetentionPolicyCog(commands.Cog):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._views_registered = False

    @property
    def bot(self) -> commands.Bot:
        return self.ctx.bot

    @property
    def client(self):
        return self.ctx.client

    @property
    def config(self):
        return self.ctx.config

    async def cog_unload(self):
        if self.purge_old_messages_via_loop.is_running():
            self.purge_old_messages_via_loop.stop()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.purge_old_messages_via_loop.is_running():
            self.purge_old_messages_via_loop.start()

        if not self._views_registered:
            self.bot.add_view(self._retention_confirmation_view())
            self._views_registered = True

    @tasks.loop(time=get_every_hour())
    async def purge_old_messages_via_loop(self):
        self.ctx.logger.info(
            f"Starting retention policy purge for messages older than {self.config.retention_period_hours} hours."
        )

        await self._purge_old_messages()

    @app_commands.command(
        name="purge_old_messages",
        description="Delete messages older than the configured retention period.",
    )
    @app_commands.guild_only()
    async def purge_old_messages(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        if interaction.guild_id != self.config.guild_id:
            await interaction.response.send_message(
                "This command can only be used in the configured server.",
                ephemeral=True,
            )
            return

        try:
            has_admin_role = await self._has_admin_role(interaction.user)
        except RuntimeError as e:
            await interaction.response.send_message(f"[ERROR] {e}", ephemeral=True)
            return

        if not has_admin_role:
            await interaction.response.send_message(
                "You do not have permission to run this command.", ephemeral=True
            )
            return

        if self.config.retention_period_hours is None:
            await interaction.response.send_message(
                "Retention is not configured.", ephemeral=True
            )
            return

        if self.config.retention_period_hours <= 0:
            await interaction.response.send_message(
                "RETENTION_PERIOD_HOURS must be a positive integer.", ephemeral=True
            )
            return

        view = self._retention_confirmation_view()

        prompt = (
            f"Are you sure you want to delete messages older than "
            f"{self.config.retention_period_hours} hour(s)?"
        )
        if self.config.dry_run:
            prompt += " This is a dry run, so nothing will be deleted."

        await interaction.response.send_message(prompt, ephemeral=True, view=view)

    async def _on_retention_confirm(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        summary = await self._purge_old_messages()

        await interaction.edit_original_response(
            content=self._format_summary(summary),
            view=None,
        )

    async def _on_retention_cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Cancelled.", view=None)

    def _retention_confirmation_view(self) -> RetentionConfirmationView:
        return RetentionConfirmationView(
            on_confirm=self._on_retention_confirm,
            on_cancel=self._on_retention_cancel,
        )

    async def _has_admin_role(self, member: discord.Member) -> bool:
        admin_role = await self.client.get_role_for_admin()
        return admin_role in member.roles

    def _format_channel_label(self, channel: ChannelWithDeleteMessages) -> str:
        mention = getattr(channel, "mention", None)
        if mention:
            return mention
        name = getattr(channel, "name", None)
        if name:
            return f"#{name}"
        return str(getattr(channel, "id", "unknown-channel"))

    def _is_skipped_channel(self, channel: ChannelWithDeleteMessages) -> bool:
        protected_ids = set(self.config.retention_protected_channel_ids)
        protected_ids.update({self.config.channel_id_rules, self.config.channel_id_log})

        channel_id = getattr(channel, "id", None)
        parent_id = getattr(channel, "parent_id", None)
        return channel_id in protected_ids or parent_id in protected_ids

    async def _purge_old_messages(self) -> PurgeSummary:
        if not self.config.retention_period_hours:
            raise ValueError("Expected retention_period_hours to be positive integer")

        guild = await self.client.get_guild()
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.config.retention_period_hours
        )
        bulk_cutoff = datetime.now(timezone.utc) - BULK_DELETE_MAX_AGE

        summary = PurgeSummary()

        channels = self._iter_target_channels(guild)
        for index, channel in enumerate(channels):
            summary.channels_checked += 1

            if self._is_skipped_channel(channel):
                continue

            try:
                if isinstance(channel, Thread):
                    channel_summary = await self._purge_thread(
                        channel=channel, cutoff=cutoff
                    )
                else:
                    channel_summary = await self._purge_channel(
                        channel=channel,
                        cutoff=cutoff,
                        bulk_cutoff=bulk_cutoff,
                    )
            except discord.Forbidden as e:
                self.ctx.logger.warning(
                    f"[WARN] Missing access while checking retention for {self._format_channel_label(channel)}: {e}",
                )
                continue
            except discord.HTTPException as e:
                self.ctx.logger.warning(
                    f"[WARN] Failed while checking retention for {self._format_channel_label(channel)}: {e}",
                )
                continue

            summary.per_channel.append(channel_summary)
            summary.deleted += channel_summary.deleted
            summary.pinned_skipped += channel_summary.pinned_skipped
            summary.channels_with_old_candidates += (
                1 if channel_summary.has_old_candidates else 0
            )
            summary.failures += channel_summary.failures
            if channel_summary.candidates:
                summary.channels_with_candidates += 1

            if index < len(channels) - 1:
                await asyncio.sleep(0.25)

        return summary

    def _iter_target_channels(
        self, guild: discord.Guild
    ) -> list[ChannelWithDeleteMessages]:
        channels: list[ChannelWithDeleteMessages] = list(guild.text_channels)
        threads = guild.threads

        for thread in threads:
            if isinstance(thread, (discord.Thread, discord.TextChannel)):
                channels.append(thread)

        return channels

    async def _purge_thread(
        self, channel: Thread, cutoff: datetime
    ) -> ChannelPurgeSummary:
        channel_label = self._format_channel_label(channel)

        if not await self._thread_should_be_considered(channel, cutoff):
            return ChannelPurgeSummary(
                channel_label=channel_label,
                candidates=0,
                pinned_skipped=0,
                delete_candidates=0,
                has_old_candidates=False,
            )

        if self.config.dry_run:
            self.ctx.logger.info(
                (
                    f"DRY RUN: {channel_label} thread would be deleted. Newest message is older than cutoff."
                )
            )
        else:
            try:
                await channel.delete()
                self.ctx.logger.info(f"Deleted old thread {channel_label}")
            except discord.Forbidden as e:
                self._log_warning_with_exception(
                    f"[WARN] Missing permissions to delete thread {channel_label}", e
                )
            except discord.HTTPException as e:
                self._log_warning_with_exception(
                    f"[WARN] Failed to delete thread {channel_label}", e
                )

        return ChannelPurgeSummary(
            channel_label=channel_label,
            candidates=0,
            pinned_skipped=0,
            delete_candidates=0,
            has_old_candidates=False,
        )

    async def _purge_channel(
        self,
        channel: TextChannel,
        cutoff: datetime,
        bulk_cutoff: datetime,
    ) -> ChannelPurgeSummary:
        channel_label = self._format_channel_label(channel)
        delete_candidates: list[discord.Message] = []
        pinned_skipped = 0

        async for message in channel.history(
            limit=None, oldest_first=True, after=bulk_cutoff, before=cutoff
        ):
            if message.pinned:
                pinned_skipped += 1
                continue
            if message.created_at <= cutoff:
                delete_candidates.append(message)

        has_old_candidates = await self._channel_has_messages_older_than_bulk_cutoff(
            channel, bulk_cutoff
        )

        if has_old_candidates:
            self.ctx.logger.warning(
                (
                    f"[WARN] {channel_label}: found non-pinned message(s) older than "
                    f"14 days; bulk delete cannot be used, so they will be skipped"
                ),
            )

        if self.config.dry_run:
            self.ctx.logger.info(
                (
                    f"DRY RUN: {channel_label} -> would delete {len(delete_candidates)} message(s) "
                    f"({pinned_skipped} pinned skipped)"
                )
            )
            return ChannelPurgeSummary(
                channel_label=channel_label,
                candidates=len(delete_candidates),
                pinned_skipped=pinned_skipped,
                delete_candidates=len(delete_candidates),
                has_old_candidates=has_old_candidates,
            )

        deleted = 0
        failures = 0

        if delete_candidates:
            for batch in chunked(delete_candidates, BULK_DELETE_CHUNK_SIZE):
                batch_deleted, batch_failures = await self._delete_recent_batch(
                    channel, batch
                )
                deleted += batch_deleted
                failures += batch_failures

            self.ctx.logger.info(
                (
                    f"Deleted {len(delete_candidates)} old messages from {channel_label} "
                    f"({pinned_skipped} pinned skipped)"
                )
            )

        return ChannelPurgeSummary(
            channel_label=channel_label,
            candidates=len(delete_candidates),
            pinned_skipped=pinned_skipped,
            delete_candidates=len(delete_candidates),
            has_old_candidates=has_old_candidates,
            deleted=deleted,
            failures=failures,
        )

    async def _channel_has_messages_older_than_bulk_cutoff(
        self, channel: ChannelWithDeleteMessages, bulk_cutoff: datetime
    ):
        async for message in channel.history(
            limit=100, oldest_first=True, before=bulk_cutoff
        ):
            if message.pinned:
                continue
            return True
        return False

    async def _thread_should_be_considered(
        self, thread: discord.Thread, cutoff: datetime
    ) -> bool:
        async for message in thread.history(limit=1, oldest_first=False):
            return message.created_at < cutoff

        return thread.created_at < cutoff if thread.created_at else False

    async def _delete_recent_batch(
        self, channel: ChannelWithDeleteMessages, batch: list[discord.Message]
    ) -> tuple[int, int]:
        if not batch:
            return 0, 0

        try:
            await channel.delete_messages(batch)
            return len(batch), 0
        except discord.Forbidden:
            self._log_warning(
                f"Missing permissions to bulk delete messages in {self._format_channel_label(channel)}"
            )
        except discord.HTTPException as e:
            self._log_warning_with_exception(
                f"Failed to bulk delete messages in {self._format_channel_label(channel)}",
                e,
            )

        return 0, len(batch)

    def _format_summary(self, summary: PurgeSummary) -> str:
        if summary.deleted == 0:
            return "No messages were deleted."

        return (
            f"Purged {summary.deleted} message(s) across {summary.channels_with_candidates} "
            f"channel(s)."
        )

    def _log_warning(self, msg: str):
        self.ctx.logger.warning(f"[WARN] {msg}")

    def _log_warning_with_exception(self, msg: str, e: Exception):
        # reason: log once to discord+local, and once to local with exception
        self.ctx.logger.warning(f"[WARN] {msg}")
        self.ctx.logger.warning(f"[WARN] {msg}: {e}", extra={"skip_discord": True})


async def setup(bot: commands.Bot, ctx: AppContext):
    await bot.add_cog(MessageRetentionPolicyCog(ctx))
