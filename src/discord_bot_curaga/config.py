from dataclasses import dataclass
import os


@dataclass
class BotConfig:
    token: str
    guild_id: int
    message_id_rules: int
    role_id_approved: int
    channel_id_log: int
    channel_id_approval: int
    approval_emoji: str
    dry_run: bool

    @staticmethod
    def create_from_env() -> "BotConfig":
        return BotConfig(
            token=os.environ["DISCORD_TOKEN"],
            guild_id=int(os.environ["GUILD_ID"]),
            message_id_rules=int(os.environ["MESSAGE_ID_RULES"]),
            role_id_approved=int(os.environ["ROLE_ID_APPROVED"]),
            channel_id_log=int(os.environ["CHANNEL_ID_LOG"]),
            channel_id_approval=int(os.environ["CHANNEL_ID_APPROVAL"]),
            approval_emoji=os.environ.get("APPROVAL_EMOJI", "👍"),
            dry_run=os.environ.get("DRY_RUN", "0").lower() in ["1", "true"],
        )
