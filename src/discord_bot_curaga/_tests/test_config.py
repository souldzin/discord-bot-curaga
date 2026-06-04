from __future__ import annotations

from discord_bot_curaga.config import AppConfig


def test_create_from_env_parses_redaction_ignore_channels(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setenv("GUILD_ID", "1")
    monkeypatch.setenv("ROLE_ID_APPROVED", "3")
    monkeypatch.setenv("ROLE_ID_ADMIN", "4")
    monkeypatch.setenv("CHANNEL_ID_LOG", "5")
    monkeypatch.setenv("CHANNEL_ID_APPROVAL", "6")
    monkeypatch.setenv("CHANNEL_ID_RULES", "7")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("REDACTION_ENABLED", "1")
    monkeypatch.setenv("REDACTION_THRESHOLD", "7")
    monkeypatch.setenv("REDACTION_EMOJI", "❌")
    monkeypatch.setenv("REDACTION_IGNORE_CHANNEL_IDS", "11, 22,33")
    monkeypatch.setenv("RETENTION_PERIOD_HOURS", "24")
    monkeypatch.setenv("RETENTION_PERIOD_PROTECTED_CHANNELS", "44,55")

    config = AppConfig.create_from_env()

    assert config.role_id_admin == 4
    assert config.channel_id_rules == 7
    assert config.dry_run is True
    assert config.redaction_enabled is True
    assert config.redaction_threshold == 7
    assert config.redaction_ignore_channel_ids == [11, 22, 33]
    assert config.retention_period_hours == 24
    assert config.retention_protected_channel_ids == [44, 55]
