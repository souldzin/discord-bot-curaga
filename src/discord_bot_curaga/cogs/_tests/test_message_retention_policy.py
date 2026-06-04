from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Awaitable, Callable, cast

from discord import Interaction
from discord.ext.commands import Bot

from unittest.mock import AsyncMock, Mock

from discord_bot_curaga.cogs import message_retention_policy as retention_module
from discord_bot_curaga.cogs.message_retention_policy import MessageRetentionPolicyCog
from discord_bot_curaga.config import AppConfig
from discord_bot_curaga.context import AppContext
from discord_bot_curaga.utils.discord_client import DiscordClient
from discord_bot_curaga.views.retention_confirmation import (
    RetentionConfirmationView,
)


@dataclass
class FakeMember:
    roles: list
    display_name: str = "Admin"
    mention: str = "@admin"


class AsyncHistoryIterator:
    def __init__(self, items):
        self._items = list(items)
        self._iter = iter(self._items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class TestRetention:
    def setup_test_subject(
        self, mocker, *, dry_run=False, retention_hours=24, protected_channel_ids=[]
    ):
        mocker.patch.object(retention_module.discord, "Member", FakeMember)

        self.config = AppConfig(
            token="token",
            guild_id=1,
            role_id_approved=3,
            role_id_admin=4,
            channel_id_log=5,
            channel_id_approval=6,
            channel_id_rules=7,
            dry_run=dry_run,
            redaction_enabled=False,
            redaction_threshold=3,
            redaction_emoji="❌",
            redaction_channel_id=None,
            redaction_ignore_channel_ids=[],
            retention_period_hours=retention_hours,
            retention_protected_channel_ids=protected_channel_ids,
        )
        self.admin_role = SimpleNamespace(id=self.config.role_id_admin)
        self.message = SimpleNamespace(
            pinned=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        self.channel = SimpleNamespace(
            id=42,
            mention="#retention-test",
            history=mocker.Mock(side_effect=self._history_side_effect),
            delete_messages=mocker.AsyncMock(),
        )
        self.guild = SimpleNamespace(
            text_channels=[self.channel],
            threads=[],
        )
        self.client = cast(
            DiscordClient,
            SimpleNamespace(
                get_role_for_admin=mocker.AsyncMock(return_value=self.admin_role),
                get_guild=mocker.AsyncMock(return_value=self.guild),
            ),
        )
        self.bot = cast(Bot, mocker.Mock(user=SimpleNamespace(id=1)))
        self.bot.add_view = mocker.Mock()
        self.bot.close = mocker.AsyncMock()
        self.ctx = AppContext(
            config=self.config,
            client=self.client,
            bot=self.bot,
            logger=mocker.Mock(),
        )
        self.subject = MessageRetentionPolicyCog(self.ctx)
        self.member = FakeMember(roles=[self.admin_role])

    def _history_side_effect(self, *args, **kwargs):
        before = kwargs.get("before")
        after = kwargs.get("after")
        limit = kwargs.get("limit")

        if before is not None and after is not None:
            return AsyncHistoryIterator([self.message])

        if limit == 100 and before is not None and after is None:
            return AsyncHistoryIterator([])

        return AsyncHistoryIterator([])

    def _make_channel(
        self,
        mocker,
        channel_id: int,
        messages: list = [],
        history_error: Exception | None = None,
    ):
        def history_side_effect(*args, **kwargs):
            if history_error:
                raise history_error

            before = kwargs.get("before")
            after = kwargs.get("after")

            items = [
                x
                for x in messages
                if (before is None or x.created_at <= before)
                and (after is None or x.created_at >= after)
            ]

            return AsyncHistoryIterator(items)

        return SimpleNamespace(
            id=channel_id,
            mention=f"#channel-{channel_id}",
            history=mocker.Mock(side_effect=history_side_effect),
            delete_messages=mocker.AsyncMock(),
        )

    def _make_interaction(self, mocker, **overrides):
        base = dict(
            user=self.member,
            guild_id=self.config.guild_id,
            response=SimpleNamespace(
                send_message=mocker.AsyncMock(),
                defer=mocker.AsyncMock(),
                edit_message=mocker.AsyncMock(),
            ),
            edit_original_response=mocker.AsyncMock(),
        )
        base.update(overrides)
        return cast(Interaction, SimpleNamespace(**base))

    def call_command(self, interaction: Interaction) -> Awaitable:
        return cast(
            Callable[[MessageRetentionPolicyCog, Interaction], Awaitable],
            self.subject.purge_old_messages.callback,
        )(self.subject, interaction)

    def test_on_ready_registers_confirmation_view(self, mocker):
        self.setup_test_subject(mocker)

        async def run():
            await self.subject.on_ready()

            as_mock(self.bot.add_view).assert_called_once()
            view = as_mock(self.bot.add_view).call_args.args[0]
            assert isinstance(view, RetentionConfirmationView)
            as_async_mock(self.bot.close).assert_not_awaited()

        asyncio.run(run())

    def test_purge_old_messages_prompts_for_confirmation(self, mocker):
        self.setup_test_subject(mocker)
        interaction = self._make_interaction(mocker)

        async def run():
            await self.call_command(interaction)

            as_async_mock(interaction.response.send_message).assert_awaited_once()
            args = as_async_mock(interaction.response.send_message).call_args.args
            kwargs = as_async_mock(interaction.response.send_message).call_args.kwargs
            assert (
                "Are you sure you want to delete messages older than 24 hour(s)?"
                in args[0]
            )
            assert kwargs["ephemeral"] is True
            assert isinstance(kwargs["view"], RetentionConfirmationView)

        asyncio.run(run())

    def test_retention_confirm_button_runs_purge_and_updates_response(self, mocker):
        self.setup_test_subject(mocker)
        interaction = self._make_interaction(mocker)

        async def run():
            await self.call_command(interaction)

            view = as_async_mock(interaction.response.send_message).call_args.kwargs[
                "view"
            ]
            confirm_button = next(
                item
                for item in view.children
                if getattr(item, "custom_id", None)
                == RetentionConfirmationView.CONFIRM_ID
            )

            confirm_interaction = self._make_interaction(
                mocker,
                response=SimpleNamespace(
                    send_message=mocker.AsyncMock(),
                    defer=mocker.AsyncMock(),
                    edit_message=mocker.AsyncMock(),
                ),
                edit_original_response=mocker.AsyncMock(),
            )

            await confirm_button.callback(confirm_interaction)

            as_async_mock(confirm_interaction.response.defer).assert_awaited_once_with(
                ephemeral=True, thinking=True
            )
            as_async_mock(self.channel.delete_messages).assert_awaited_once()
            as_async_mock(
                confirm_interaction.edit_original_response
            ).assert_awaited_once()
            assert (
                as_async_mock(
                    confirm_interaction.edit_original_response
                ).call_args.kwargs["content"]
                == "Purged 1 message(s) across 1 channel(s)."
            )
            assert (
                as_async_mock(
                    confirm_interaction.edit_original_response
                ).call_args.kwargs["view"]
                is None
            )

        asyncio.run(run())

    def test_retention_skips_protected_rules_and_log_channels(self, mocker):
        self.setup_test_subject(mocker, protected_channel_ids=[99])

        eligible_message = SimpleNamespace(
            pinned=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=30),
        )

        normal_channel = self._make_channel(mocker, 100, [eligible_message])
        protected_channel = self._make_channel(
            mocker,
            99,
            history_error=AssertionError(
                "history() should not be called for skipped channels"
            ),
        )
        rules_channel = self._make_channel(
            mocker,
            self.config.channel_id_rules,
            history_error=AssertionError(
                "history() should not be called for skipped channels"
            ),
        )
        log_channel = self._make_channel(
            mocker,
            self.config.channel_id_log,
            history_error=AssertionError(
                "history() should not be called for skipped channels"
            ),
        )

        self.guild = SimpleNamespace(
            text_channels=[
                normal_channel,
                protected_channel,
                rules_channel,
                log_channel,
            ],
            threads=[],
        )
        self.client.get_guild = mocker.AsyncMock(return_value=self.guild)

        interaction = self._make_interaction(mocker)

        async def run():
            await self.call_command(interaction)

            view = as_async_mock(interaction.response.send_message).call_args.kwargs[
                "view"
            ]
            confirm_button = next(
                item
                for item in view.children
                if getattr(item, "custom_id", None)
                == RetentionConfirmationView.CONFIRM_ID
            )

            confirm_interaction = self._make_interaction(
                mocker,
                response=SimpleNamespace(
                    send_message=mocker.AsyncMock(),
                    defer=mocker.AsyncMock(),
                    edit_message=mocker.AsyncMock(),
                ),
                edit_original_response=mocker.AsyncMock(),
            )

            await confirm_button.callback(confirm_interaction)

            as_async_mock(normal_channel.delete_messages).assert_awaited_once_with(
                [eligible_message]
            )
            as_async_mock(protected_channel.delete_messages).assert_not_awaited()
            as_async_mock(rules_channel.delete_messages).assert_not_awaited()
            as_async_mock(log_channel.delete_messages).assert_not_awaited()
            as_async_mock(
                confirm_interaction.edit_original_response
            ).assert_awaited_once()
            assert (
                as_async_mock(
                    confirm_interaction.edit_original_response
                ).call_args.kwargs["content"]
                == "Purged 1 message(s) across 1 channel(s)."
            )

        asyncio.run(run())

    def test_retention_deletes_recent_messages_and_skips_old_pinned_messages(
        self, mocker
    ):
        self.setup_test_subject(mocker)

        delete_message = SimpleNamespace(
            pinned=False,
            created_at=datetime.now(timezone.utc) - timedelta(hours=30),
        )
        old_pinned_message = SimpleNamespace(
            pinned=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        deleted_batches = []

        async def delete_messages(batch):
            deleted_batches.append(list(batch))

        channel = self._make_channel(
            mocker, 100, messages=[delete_message, old_pinned_message]
        )
        channel.delete_messages = AsyncMock(side_effect=delete_messages)
        self.guild = SimpleNamespace(text_channels=[channel], threads=[])
        self.client.get_guild = mocker.AsyncMock(return_value=self.guild)

        interaction = self._make_interaction(mocker)

        async def run():
            await self.call_command(interaction)

            view = as_async_mock(interaction.response.send_message).call_args.kwargs[
                "view"
            ]
            confirm_button = next(
                item
                for item in view.children
                if getattr(item, "custom_id", None)
                == RetentionConfirmationView.CONFIRM_ID
            )

            confirm_interaction = self._make_interaction(
                mocker,
                response=SimpleNamespace(
                    send_message=mocker.AsyncMock(),
                    defer=mocker.AsyncMock(),
                    edit_message=mocker.AsyncMock(),
                ),
                edit_original_response=mocker.AsyncMock(),
            )

            await confirm_button.callback(confirm_interaction)

            assert deleted_batches == [[delete_message]]
            assert channel.history.call_count == 2
            assert channel.history.call_args_list[0].kwargs["after"] is not None
            assert channel.history.call_args_list[0].kwargs["before"] is not None
            assert channel.history.call_args_list[1].kwargs["limit"] == 100
            assert channel.history.call_args_list[1].kwargs["before"] is not None
            as_async_mock(
                confirm_interaction.edit_original_response
            ).assert_awaited_once()
            assert (
                as_async_mock(
                    confirm_interaction.edit_original_response
                ).call_args.kwargs["content"]
                == "Purged 1 message(s) across 1 channel(s)."
            )

        asyncio.run(run())


def as_async_mock(thing):
    return cast(AsyncMock, thing)


def as_mock(thing):
    return cast(Mock, thing)
