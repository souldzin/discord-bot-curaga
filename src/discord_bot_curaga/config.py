from dataclasses import dataclass
import os


def _optional_int_env(name: str) -> int | None:
    value = os.environ.get(name)
    if value in (None, "", "0"):
        return None
    return int(value)


def _optional_int_list_env(name: str) -> list[int]:
    value = os.environ.get(name, "")
    if not value.strip():
        return []

    return [int(item.strip()) for item in value.split(",") if item.strip()]


@dataclass
class AppConfig:
    token: str
    guild_id: int
    role_id_approved: int
    role_id_admin: int
    channel_id_log: int
    channel_id_approval: int
    channel_id_rules: int
    dry_run: bool
    redaction_enabled: bool
    redaction_threshold: int
    redaction_emoji: str
    redaction_channel_id: int | None
    redaction_ignore_channel_ids: list[int]

    @staticmethod
    def create_from_env() -> "AppConfig":
        return AppConfig(
            token=os.environ["DISCORD_TOKEN"],
            guild_id=int(os.environ["GUILD_ID"]),
            role_id_approved=int(os.environ["ROLE_ID_APPROVED"]),
            role_id_admin=int(os.environ["ROLE_ID_ADMIN"]),
            channel_id_log=int(os.environ["CHANNEL_ID_LOG"]),
            channel_id_approval=int(os.environ["CHANNEL_ID_APPROVAL"]),
            channel_id_rules=int(os.environ["CHANNEL_ID_RULES"]),
            dry_run=os.environ.get("DRY_RUN", "0").lower() in ["1", "true"],
            redaction_enabled=os.environ.get("REDACTION_ENABLED", "0").lower()
            in ["1", "true"],
            redaction_threshold=int(os.environ.get("REDACTION_THRESHOLD", "3")),
            redaction_emoji=os.environ.get("REDACTION_EMOJI", "❌"),
            redaction_channel_id=_optional_int_env("REDACTION_CHANNEL_ID"),
            redaction_ignore_channel_ids=_optional_int_list_env(
                "REDACTION_IGNORE_CHANNEL_IDS"
            ),
        )
