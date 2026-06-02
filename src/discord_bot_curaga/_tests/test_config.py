from __future__ import annotations

from discord_bot_curaga.config import AppConfig


def test_create_from_env_parses_redaction_ignore_channels(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setenv("GUILD_ID", "1")
    monkeypatch.setenv("MESSAGE_ID_RULES", "2")
    monkeypatch.setenv("ROLE_ID_APPROVED", "3")
    monkeypatch.setenv("CHANNEL_ID_LOG", "4")
    monkeypatch.setenv("CHANNEL_ID_APPROVAL", "5")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("REDACTION_ENABLED", "1")
    monkeypatch.setenv("REDACTION_THRESHOLD", "7")
    monkeypatch.setenv("REDACTION_EMOJI", "❌")
    monkeypatch.setenv("REDACTION_IGNORE_CHANNEL_IDS", "11, 22,33")

    config = AppConfig.create_from_env()

    assert config.dry_run is True
    assert config.redaction_enabled is True
    assert config.redaction_threshold == 7
    assert config.redaction_ignore_channel_ids == [11, 22, 33]
