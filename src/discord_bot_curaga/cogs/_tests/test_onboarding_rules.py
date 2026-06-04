from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import cast

from discord import Interaction, RawReactionActionEvent
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


def setup_discord_patch(mocker):
    mocker.patch.object(onboarding_module.discord, "Member", FakeMember)


def as_async_mock(thing):
    return cast(AsyncMock, thing)


def as_mock(thing):
    return cast(Mock, thing)


class TestOnboardingRules:
    def setup_test_subject(self, mocker, *, approved_roles=None):
        setup_discord_patch(mocker)

        self.config = _make_config()
        self.approved_role = SimpleNamespace(name="Approved")
        self.client = cast(
            DiscordClient,
            SimpleNamespace(
                get_guild=mocker.AsyncMock(),
                get_channel_approval=mocker.AsyncMock(),
                get_role_for_approved=mocker.AsyncMock(return_value=self.approved_role),
                get_guild_member=mocker.AsyncMock(),
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
            response=SimpleNamespace(send_message=mocker.AsyncMock()),
            followup=SimpleNamespace(send=mocker.AsyncMock()),
        )
        base.update(overrides)
        return cast(Interaction, SimpleNamespace(**base))

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
