import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Awaitable, Callable, cast

import discord
from discord import Interaction
from discord.ext.commands import Bot

from unittest.mock import AsyncMock, Mock

from discord_bot_curaga.cogs import onboarding as onboarding_module
from discord_bot_curaga.cogs.onboarding import OnboardingCog
from discord_bot_curaga.config import AppConfig
from discord_bot_curaga.context import AppContext
from discord_bot_curaga.utils.discord_client import DiscordClient
from discord_bot_curaga.views.approval_request import ApprovalRequestView


def _make_config():
    return AppConfig(
        token="token",
        guild_id=1,
        role_id_approved=3,
        role_id_admin=4,
        channel_id_log=5,
        channel_id_approval=6,
        channel_id_rules=7,
        dry_run=False,
        redaction_enabled=False,
        redaction_threshold=3,
        redaction_emoji="❌",
        redaction_channel_id=None,
        redaction_ignore_channel_ids=[],
    )


@dataclass
class FakeMember:
    roles: list
    display_name: str
    mention: str


@dataclass
class FakeChannel:
    id: int
    history: Mock
    delete_messages: AsyncMock


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


def setup_discord_patch(mocker):
    mocker.patch.object(onboarding_module.discord, "Member", FakeMember)
    mocker.patch.object(onboarding_module, "ChannelWithDeleteMessages", FakeChannel)


def as_async_mock(thing):
    return cast(AsyncMock, thing)


def as_mock(thing):
    return cast(Mock, thing)


class TestOnboardingRules:
    def setup_test_subject(self, mocker, *, approved_roles=None):
        setup_discord_patch(mocker)

        self.config = _make_config()
        self.approved_role = SimpleNamespace(name="Approved")
        self.admin_role = SimpleNamespace(name="Admin")
        self.approval_channel = FakeChannel(
            id=self.config.channel_id_approval,
            history=mocker.Mock(return_value=AsyncHistoryIterator([])),
            delete_messages=mocker.AsyncMock(),
        )
        self.client = cast(
            DiscordClient,
            SimpleNamespace(
                get_guild=mocker.AsyncMock(),
                get_channel_approval=mocker.AsyncMock(
                    return_value=self.approval_channel
                ),
                get_role_for_approved=mocker.AsyncMock(return_value=self.approved_role),
                get_guild_member=mocker.AsyncMock(),
                get_role_for_admin=mocker.AsyncMock(return_value=self.admin_role),
            ),
        )

        self.bot = cast(Bot, mocker.Mock(user=SimpleNamespace(id=1)))
        self.bot.add_view = mocker.Mock()
        self.bot.close = mocker.AsyncMock()
        self.bot.get_cog = mocker.Mock(return_value=None)

        self.member = FakeMember(
            roles=approved_roles or [],
            display_name="Test User",
            mention="@test",
        )

        self.ctx = AppContext(
            config=self.config,
            client=self.client,
            bot=self.bot,
            logger=mocker.Mock(),
        )
        self.subject = OnboardingCog(self.ctx)

    def _make_interaction(self, mocker, **overrides):
        base = dict(
            user=self.member,
            guild_id=self.config.guild_id,
            response=SimpleNamespace(
                send_message=mocker.AsyncMock(), defer=mocker.AsyncMock()
            ),
            followup=SimpleNamespace(send=mocker.AsyncMock()),
            edit_original_response=mocker.AsyncMock(),
        )
        base.update(overrides)
        return cast(Interaction, SimpleNamespace(**base))

    def call_purge_approval_requests(
        self, interaction: Interaction, minutes: int = 10
    ) -> Awaitable:
        return cast(
            Callable[[OnboardingCog, Interaction, int | None], Awaitable],
            self.subject.purge_approval_requests.callback,
        )(self.subject, interaction, minutes)

    def test_on_ready_registers_persistent_views(self, mocker):
        self.setup_test_subject(mocker)

        async def run():
            await self.subject.on_ready()

            as_mock(self.bot.add_view).assert_called_once()
            view = as_mock(self.bot.add_view).call_args.args[0]
            assert isinstance(view, ApprovalRequestView)
            as_async_mock(self.bot.close).assert_not_awaited()

        asyncio.run(run())

    def test_rules_ack_button_sends_ephemeral_confirmation(self, mocker):
        self.setup_test_subject(mocker)
        self.subject._post_approval_request = mocker.AsyncMock()
        interaction = self._make_interaction(mocker)

        async def run():
            await self.subject.on_rules_acknowledge(interaction)

            as_async_mock(interaction.response.send_message).assert_awaited_once_with(
                "Thanks for accepting the rules! We'll let the mods know you're here.",
                ephemeral=True,
            )
            as_async_mock(self.subject._post_approval_request).assert_awaited_once_with(
                self.member
            )

        asyncio.run(run())

    def test_rules_ack_button_short_circuits_when_already_approved(self, mocker):
        approved_role = SimpleNamespace(name="Approved")
        self.setup_test_subject(mocker, approved_roles=[approved_role])
        self.client.get_role_for_approved = mocker.AsyncMock(return_value=approved_role)
        self.subject._post_approval_request = mocker.AsyncMock()
        interaction = self._make_interaction(mocker)

        async def run():
            await self.subject.on_rules_acknowledge(interaction)

            as_async_mock(interaction.response.send_message).assert_awaited_once_with(
                "Thanks for accepting the rules again - you already have access.",
                ephemeral=True,
            )
            as_async_mock(self.subject._post_approval_request).assert_not_awaited()

        asyncio.run(run())

    def _make_approval_message(
        self, mocker, *, message_id: int, minutes_ago: int, status: str
    ):
        embed = discord.Embed(
            title="Approval Request", description="member requested access"
        )
        embed.add_field(name="Member", value="Test User (`123`)", inline=False)
        embed.add_field(name="Status", value=status, inline=False)
        embed.set_footer(text="member_id:123")

        message = mocker.Mock()
        message.id = message_id
        message.author = SimpleNamespace(id=1, bot=True)
        message.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        message.embeds = [embed]
        message.delete = mocker.AsyncMock()
        return message

    def test_purge_approval_requests_deletes_only_resolved_old_messages(self, mocker):
        self.setup_test_subject(mocker)

        old_approved = self._make_approval_message(
            mocker, message_id=101, minutes_ago=30, status="Approved ✅ by @mod"
        )
        old_pending = self._make_approval_message(
            mocker, message_id=102, minutes_ago=25, status="Pending ⏳"
        )
        old_rejected = self._make_approval_message(
            mocker, message_id=103, minutes_ago=20, status="Rejected ❌ by @mod"
        )
        recent_approved = self._make_approval_message(
            mocker, message_id=104, minutes_ago=1, status="Approved ✅ by @mod"
        )
        self.approval_channel.history = mocker.Mock(
            return_value=AsyncHistoryIterator(
                [old_approved, old_pending, old_rejected, recent_approved]
            )
        )

        async def run():
            self.member.roles.append(self.admin_role)
            interaction = self._make_interaction(mocker)

            await self.call_purge_approval_requests(interaction)

            as_async_mock(interaction.response.defer).assert_awaited_once_with(
                ephemeral=True, thinking=True
            )
            as_async_mock(
                self.approval_channel.delete_messages
            ).assert_awaited_once_with([old_approved, old_rejected])
            as_async_mock(old_approved.delete).assert_not_awaited()
            as_async_mock(old_rejected.delete).assert_not_awaited()
            as_async_mock(old_pending.delete).assert_not_awaited()
            as_async_mock(recent_approved.delete).assert_not_awaited()
            assert "Purged 2 resolved approval request(s)" in (
                as_async_mock(interaction.edit_original_response).call_args.kwargs[
                    "content"
                ]
            )

        asyncio.run(run())

    def test_purge_approval_requests_keeps_pending_messages(self, mocker):
        self.setup_test_subject(mocker)

        pending = self._make_approval_message(
            mocker, message_id=201, minutes_ago=30, status="Pending ⏳"
        )
        self.approval_channel.history = mocker.Mock(
            return_value=AsyncHistoryIterator([pending])
        )

        async def run():
            self.member.roles.append(self.admin_role)
            interaction = self._make_interaction(mocker)

            await self.call_purge_approval_requests(interaction, 10)

            as_async_mock(pending.delete).assert_not_awaited()
            as_async_mock(self.approval_channel.delete_messages).assert_not_awaited()
            as_async_mock(interaction.edit_original_response).assert_awaited_with(
                content="No messages found to delete."
            )

        asyncio.run(run())
