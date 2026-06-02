# Curaga: A Discord Bot

This is a simple Discord bot equipped with some random magic.

## Features

### Onboarding workflow

1. A user reacts with `👍` (or configured emoji) on the rules message.
2. The bot DMs the user that a moderator will review soon.
3. The bot posts an approval request embed in the approval channel.
4. Moderators click **Approve** or **Reject**.
5. On **Approve**, the bot assigns the configured approved role.

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

# Rules message ID users react to
MESSAGE_ID_RULES=

# Role assigned when approved
ROLE_ID_APPROVED=

# Bot log channel ID (optional but recommended)
CHANNEL_ID_LOG=

# Moderator approval channel ID
CHANNEL_ID_APPROVAL=

# Emoji that triggers onboarding reaction
APPROVAL_EMOJI=👍

# If '1' or 'true', bot logs actions but does not assign roles
DRY_RUN=0
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
