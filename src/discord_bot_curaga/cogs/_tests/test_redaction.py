from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast

from discord import RawReactionActionEvent, TextChannel

from discord_bot_curaga.cogs.redaction import RedactionCog
from discord_bot_curaga.config import AppConfig
from discord_bot_curaga.context import AppContext


def _make_config(**overrides):
    return AppConfig(
        token="token",
        guild_id=1,
        message_id_rules=99,
        role_id_approved=3,
        role_id_admin=4,
        channel_id_log=5,
        channel_id_approval=6,
        channel_id_rules=7,
        approval_emoji="👍",
        dry_run=False,
        redaction_enabled=True,
        redaction_threshold=overrides.get("redaction_threshold", 3),
        redaction_emoji="❌",
        redaction_channel_id=None,
        redaction_ignore_channel_ids=[8, 9],
    )


def _make_ctx(mocker, config, bot=None):
    return cast(
        AppContext,
        SimpleNamespace(
            config=config,
            bot=bot or mocker.Mock(user=None),
            logger=mocker.Mock(),
        ),
    )


def _make_payload(**overrides):
    base = dict(
        guild_id=1,
        user_id=123,
        message_id=100,
        channel_id=7,
        emoji="❌",
    )
    base.update(overrides)
    return cast(RawReactionActionEvent, SimpleNamespace(**base))


def _make_fake_message(mocker):
    message = mocker.Mock()
    message.id = 1234
    message.author = SimpleNamespace(bot=False, mention="@user")
    message.reactions = [SimpleNamespace(emoji="❌", count=3)]
    message.delete = mocker.AsyncMock()

    return message


def _make_fake_channel(mocker, message):
    channel = mocker.Mock(spec=TextChannel)
    channel.fetch_message = mocker.AsyncMock(return_value=message)
    channel.send = mocker.AsyncMock()
    message.channel = channel

    return channel


def _make_fake_bot(mocker, channel):
    bot = mocker.Mock(user=None)
    bot.get_channel.return_value = channel
    bot.fetch_channel = mocker.AsyncMock()

    return bot


def test_on_raw_reaction_add_ignores_rules_message(mocker):
    async def run():
        config = _make_config()
        bot = mocker.Mock(user=None)
        bot.get_channel = mocker.Mock()
        bot.fetch_channel = mocker.AsyncMock()
        cog = RedactionCog(_make_ctx(mocker, config, bot=bot))

        await cog.on_raw_reaction_add(_make_payload(message_id=config.message_id_rules))

        bot.get_channel.assert_not_called()
        bot.fetch_channel.assert_not_called()

    asyncio.run(run())


def test_on_raw_reaction_add_ignores_configured_channels(mocker):
    async def run():
        config = _make_config()
        bot = mocker.Mock(user=None)
        bot.get_channel = mocker.Mock()
        bot.fetch_channel = mocker.AsyncMock()
        cog = RedactionCog(_make_ctx(mocker, config, bot=bot))

        await cog.on_raw_reaction_add(_make_payload(channel_id=8))

        bot.get_channel.assert_not_called()
        bot.fetch_channel.assert_not_called()

    asyncio.run(run())


def test_on_0_reaction_threshold(mocker):
    async def run():
        config = _make_config(redaction_threshold=0)
        message = _make_fake_message(mocker)
        channel = _make_fake_channel(mocker, message)
        bot = _make_fake_bot(mocker, channel)
        ctx = _make_ctx(mocker, config, bot=bot)

        cog = RedactionCog(ctx)
        await cog.on_raw_reaction_add(_make_payload())

        bot.get_channel.assert_not_called()
        bot.fetch_channel.assert_not_called()

    asyncio.run(run())


def test_on_raw_reaction_add_redacts_matching_message(mocker):
    async def run():
        config = _make_config()
        message = _make_fake_message(mocker)
        channel = _make_fake_channel(mocker, message)
        bot = _make_fake_bot(mocker, channel)
        ctx = _make_ctx(mocker, config, bot=bot)

        cog = RedactionCog(ctx)
        await cog.on_raw_reaction_add(_make_payload())

        bot.get_channel.assert_called_once_with(7)
        channel.fetch_message.assert_awaited_once_with(100)
        message.delete.assert_awaited_once()
        channel.send.assert_awaited_once()
        assert "redacted" in channel.send.await_args.args[0]

    asyncio.run(run())
