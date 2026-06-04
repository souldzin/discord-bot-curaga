from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Awaitable, Callable, cast

from discord import Interaction
from discord.ext.commands import Bot

import discord_bot_curaga.cogs.server_rules as server_rules_module
from discord_bot_curaga.cogs.onboarding import OnboardingCog
from discord_bot_curaga.cogs.server_rules import ServerRulesCog
from discord_bot_curaga.config import AppConfig
from discord_bot_curaga.context import AppContext
from discord_bot_curaga.test_helpers.matchers import MatchContains, MatchInstanceOf
from discord_bot_curaga.utils.discord_client import DiscordClient
from discord_bot_curaga.utils.parse_args import parse_comma_separated_ids
from discord_bot_curaga.views.rules_acknowledgement import RulesAcknowledgementView

from unittest.mock import Mock, AsyncMock


class FakeMember:
    def __init__(self, roles):
        self.roles = roles
        self.display_name = "Admin"

    def __str__(self):
        return "Admin"


class FakeTextChannel:
    def __init__(self, channel_id: int):
        self.id = channel_id
        self.send = None
        self.purge = None


def _make_config(**overrides):
    return AppConfig(
        token="token",
        guild_id=1,
        role_id_approved=3,
        role_id_admin=4,
        channel_id_log=5,
        channel_id_approval=6,
        channel_id_rules=7,
        dry_run=overrides.get("dry_run", False),
        redaction_enabled=False,
        redaction_threshold=3,
        redaction_emoji="❌",
        redaction_channel_id=None,
        redaction_ignore_channel_ids=[],
        retention_period_hours=0,
        retention_protected_channel_ids=[],
    )


def _patch_discord_channels(mocker):
    mocker.patch.object(server_rules_module.discord, "Member", FakeMember)
    mocker.patch.object(server_rules_module.discord, "TextChannel", FakeTextChannel)
    mocker.patch.object(server_rules_module.discord, "Thread", FakeTextChannel)


def _make_bot(mocker):
    bot = mocker.Mock(user=SimpleNamespace(id=1))
    bot.add_view = mocker.Mock()
    bot.close = mocker.AsyncMock()

    return cast(Bot, bot)


def _make_ctx(mocker, config, client, bot=None):
    return SimpleNamespace(
        config=config,
        client=client,
        bot=bot or mocker.Mock(user=None),
        logger=mocker.Mock(),
    )


def _make_interaction(mocker, user, channel):
    return cast(
        Interaction,
        SimpleNamespace(
            user=user,
            channel=channel,
            response=SimpleNamespace(
                send_message=mocker.AsyncMock(),
                defer=mocker.AsyncMock(),
            ),
            edit_original_response=mocker.AsyncMock(),
        ),
    )


def _make_admin_client(mocker, admin_role, rules_channel, approval_channel):
    return cast(
        DiscordClient,
        SimpleNamespace(
            get_role_for_admin=mocker.AsyncMock(return_value=admin_role),
            fetch_message=mocker.AsyncMock(),
            get_channel_rules=mocker.AsyncMock(return_value=rules_channel),
            get_channel_approval=mocker.AsyncMock(return_value=approval_channel),
        ),
    )


def as_async_mock(thing):
    return cast(AsyncMock, thing)


def as_mock(thing):
    return cast(Mock, thing)


class TestServerRules:
    def setup_test_subject(self, mocker, with_config: dict | None = None):

        self.config = _make_config(**(with_config or {}))
        self.rules_channel = SimpleNamespace(
            send=mocker.AsyncMock(),
            purge=mocker.AsyncMock(),
            id=self.config.channel_id_rules,
        )
        self.admin_role = SimpleNamespace(id=self.config.role_id_admin)
        self.client = _make_admin_client(
            mocker,
            admin_role=self.admin_role,
            rules_channel=self.rules_channel,
            approval_channel=SimpleNamespace(),
        )
        self.bot = _make_bot(mocker)
        self.ctx = AppContext(
            config=self.config,
            client=self.client,
            bot=self.bot,
            logger=mocker.Mock(),
        )

        self.onboarding_cog = OnboardingCog(self.ctx)
        self.bot.get_cog = mocker.Mock(return_value=self.onboarding_cog)

        self.subject = ServerRulesCog(self.ctx)

    def call_command(self, interaction: Interaction, message_ids: str) -> Awaitable:
        return cast(
            Callable[[ServerRulesCog, Interaction, str], Awaitable],
            self.subject.curaga_rules_sync.callback,
        )(self.subject, interaction, message_ids)

    def test_server_rules_on_ready_registers_rules_view(self, mocker):
        self.setup_test_subject(mocker)

        async def run():
            await self.subject.on_ready()

            as_async_mock(self.bot.get_cog).assert_called_once_with("OnboardingCog")
            as_async_mock(self.bot.add_view).assert_called_once_with(
                MatchInstanceOf(RulesAcknowledgementView)
            )
            actual_callback = (
                as_async_mock(self.bot.add_view).call_args.args[0].children[0].callback
            )
            assert actual_callback == self.onboarding_cog.on_rules_acknowledge
            as_async_mock(self.bot.close).assert_not_awaited()

        asyncio.run(run())

    def test_curaga_rules_sync_rejects_non_admin(self, mocker):
        _patch_discord_channels(mocker)
        self.setup_test_subject(mocker)

        async def run():
            interaction = _make_interaction(mocker, FakeMember([]), FakeTextChannel(7))

            await self.call_command(interaction, "101")

            as_async_mock(interaction.response.send_message).assert_awaited_once()
            as_async_mock(interaction.response.defer).assert_not_awaited()
            as_async_mock(self.client.fetch_message).assert_not_awaited()

        asyncio.run(run())

    def test_curaga_rules_sync_rejects_invalid_message_ids(self, mocker):
        _patch_discord_channels(mocker)
        self.setup_test_subject(mocker)

        async def run():
            interaction = _make_interaction(
                mocker, FakeMember([self.admin_role]), FakeTextChannel(7)
            )

            await self.call_command(interaction, "not-a-number")

            as_async_mock(interaction.response.send_message).assert_awaited_once()
            as_async_mock(interaction.response.defer).assert_not_awaited()
            as_async_mock(self.client.fetch_message).assert_not_awaited()

        asyncio.run(run())

    def test_curaga_rules_sync_fails_fast_when_source_message_missing(self, mocker):
        _patch_discord_channels(mocker)
        self.setup_test_subject(mocker)

        async def run():
            as_async_mock(self.client.fetch_message).side_effect = [
                SimpleNamespace(content="one"),
                None,
            ]
            as_async_mock(self.client.get_channel_rules).return_value = (
                self.rules_channel
            )
            interaction = _make_interaction(
                mocker, FakeMember([self.admin_role]), FakeTextChannel(7)
            )

            await self.call_command(interaction, "101, 102")

            as_async_mock(interaction.response.defer).assert_awaited_once_with(
                ephemeral=True, thinking=True
            )
            as_async_mock(interaction.edit_original_response).assert_awaited_once_with(
                content=MatchContains("Could not fetch source message")
            )

            as_async_mock(self.rules_channel.send).assert_not_called()
            as_async_mock(self.rules_channel.purge).assert_not_called()

        asyncio.run(run())

    def test_curaga_rules_sync_logs_dry_run_plan(self, mocker):
        _patch_discord_channels(mocker)
        self.setup_test_subject(mocker, with_config={"dry_run": True})

        async def run():
            as_async_mock(self.client.fetch_message).side_effect = [
                SimpleNamespace(id=101, content="one"),
                SimpleNamespace(id=102, content="two"),
            ]
            interaction = _make_interaction(
                mocker, FakeMember([self.admin_role]), FakeTextChannel(7)
            )

            await self.call_command(interaction, "101,102")

            as_async_mock(self.rules_channel.send).assert_not_awaited()
            as_async_mock(self.rules_channel.purge).assert_not_awaited()
            as_async_mock(interaction.edit_original_response).assert_awaited_once_with(
                content="Dry run complete. No changes were made."
            )
            assert any(
                "DRY RUN: would update rules channel" in call.args[0]
                for call in as_mock(self.ctx.logger.info).call_args_list
            )

        asyncio.run(run())

    def test_parse_message_ids_handles_spaces_and_commas(self, mocker):
        self.setup_test_subject(mocker)

        assert parse_comma_separated_ids("101,  102 103") == [101, 102, 103]
        assert parse_comma_separated_ids("bad, 102") == []

    def test_curaga_rules_sync_rewrites_rules_channel(self, mocker):
        _patch_discord_channels(mocker)
        self.setup_test_subject(mocker)

        async def run():
            interaction = _make_interaction(
                mocker, FakeMember([self.admin_role]), FakeTextChannel(7)
            )

            await self.call_command(interaction, "101,102")

            send_mock = as_async_mock(self.rules_channel.send)
            send_mock.assert_awaited()
            assert send_mock.await_args_list[0].args[0] == "Updating server rules..."
            assert (
                send_mock.await_args_list[-1].kwargs["embed"].description
                == "I have read, understand, and will adhere to the above server rules and guidelines."
            )
            assert send_mock.await_args_list[-1].kwargs["view"] == MatchInstanceOf(
                RulesAcknowledgementView
            )
            as_async_mock(self.rules_channel.purge).assert_awaited_once_with(limit=None)
            as_async_mock(interaction.edit_original_response).assert_awaited_once_with(
                content="Rules channel updated."
            )

        asyncio.run(run())
