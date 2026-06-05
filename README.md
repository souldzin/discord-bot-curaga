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
8. Admins can run `/purge_approval_requests` to clean up resolved requests.

### Redaction

- Optional redaction mode can delete messages after enough `REDACTION_EMOJI` reactions.
- Redaction can be scoped with `REDACTION_CHANNEL_ID` and/or `REDACTION_IGNORE_CHANNEL_IDS`.

### Retention Policy

- Optional retention cleanup deletes old messages after `RETENTION_PERIOD_HOURS`.
- Text channels: delete messages older than the cutoff.
- Threads: delete the whole thread if its newest message is older than the cutoff.
- Pinned messages are skipped.
- `RETENTION_PERIOD_PROTECTED_CHANNELS` can be used to exclude channel IDs (including forum parents / thread parents).
- The rules channel and log channel are always skipped.
- Retention can be run manually via `/purge_old_messages`, and it also has an hourly background task.

### Notes

- Approval buttons are persistent across restarts.
- `DRY_RUN` is pragmatic, not pure: it still posts the approval/rules views so you can test the flow, but it avoids the meaningful side-effect (role assignment) and doesn’t leave lasting state behind.
- The bot logs status and warnings to the log channel.
- A heartbeat message is posted every 10 minutes.
- Admins can purge resolved approval requests with `/purge_approval_requests`.

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

# Bot log channel ID
CHANNEL_ID_LOG=

# Moderator approval channel ID
CHANNEL_ID_APPROVAL=

# Rules channel used by /rules_sync
CHANNEL_ID_RULES=

# If '1' or 'true', bot logs actions but does not assign roles
DRY_RUN=0

# Retention cleanup (delete messages older than this many hours)
RETENTION_PERIOD_HOURS=
# Optional comma-separated channel IDs that should never be considered for retention cleanup
RETENTION_PERIOD_PROTECTED_CHANNELS=

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
