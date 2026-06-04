# Curaga: A Discord Bot

This is a simple Discord bot equipped with some random magic.

## Features

### Onboarding

1. Admins can run `/rules_sync` to rebuild the rules channel from source message IDs.
2. The final rules post uses a persistent **I Agree** button.
3. A user acknowledges the rules via the button flow.
4. The bot sends the user an ephemeral confirmation.
5. The bot posts an approval request embed in the approval channel.
6. Moderators click **Approve** or **Reject**.
7. On **Approve**, the bot assigns the configured approved role.

### Redaction

- Optional redaction mode can delete messages after enough `REDACTION_EMOJI` reactions.
- Redaction can be scoped with `REDACTION_CHANNEL_ID` and/or `REDACTION_IGNORE_CHANNEL_IDS`.

### Onboarding (Legacy)

- The legacy flow still supports acknowledging the rules via reaction on the old rules message.
- This path is kept for migration, but is intended to be removed later.

Notes:

- Approval buttons are persistent across restarts.
- The bot logs status and warnings to the log channel.
- A heartbeat message is posted every 10 minutes.

## Configuration

Create a `.env` file (you can copy from `.env.example` if present):

```env
# Discord bot token
DISCORD_TOKEN=

# Discord server ID
GUILD_ID=

# Role assigned when approved
ROLE_ID_APPROVED=

# Role allowed to run admin-only commands
ROLE_ID_ADMIN=

# Bot log channel ID (optional but recommended)
CHANNEL_ID_LOG=

# Moderator approval channel ID
CHANNEL_ID_APPROVAL=

# Rules channel used by /curaga_rules_sync
CHANNEL_ID_RULES=

# Emoji that triggers onboarding reaction
APPROVAL_EMOJI=👍

# If '1' or 'true', bot logs actions but does not assign roles
DRY_RUN=0

# Redaction feature (delete and replace messages after enough ❌ reactions)
REDACTION_ENABLED=0
REDACTION_THRESHOLD=3
REDACTION_EMOJI=❌
# Optional comma-separated list of channels to ignore for redaction
REDACTION_IGNORE_CHANNEL_IDS=
```

## Run locally

```bash
mise install
make pip_install
python3 -m discord_bot_curaga
```

## Docker

Build and run:

```bash
docker build -t discord-bot-curaga .
docker run --env-file .env discord-bot-curaga
```
