# Plan: Retention Period

- Add new env variable `RETENTION_PERIOD_HOURS` (number of hours to retain messages).
- Delete messages older than `RETENTION_PERIOD_HOURS`.
- Use bulk delete for messages newer than 14 days; if a message older than 14 days is found, log a warning and fall back as needed.
- Skip pinned messages.
- Skip the rules channel and the log channel by default.
- Add optional env var `RETENTION_PERIOD_PROTECTED_CHANNELS` for channel IDs that should never be considered.
- Use the chunk utility to batch deletes.
- The retention purge should require the admin role.
- `DRY_RUN` should log per-channel message counts instead of deleting.
- Thread strategy: judge eligibility by the oldest non-pinned message in the thread.
- Trigger via `/purge_old_messages` with an ephemeral confirmation prompt and Yes/No buttons.
- For now, keep it manual only; once validated, hook it into an hourly task.

## File-by-file plan

### `src/discord_bot_curaga/config.py`
- Add `RETENTION_PERIOD_HOURS` parsing.
- Add `RETENTION_PERIOD_PROTECTED_CHANNELS` parsing.

### `src/discord_bot_curaga/cogs/retention.py` (new)
- Implement `/purge_old_messages`.
- Admin role check.
- Confirmation flow with Yes/No buttons.
- Purge logic, including dry-run mode.
- Skip rules/log/protected channels, pinned messages, and thread eligibility rules.

### `src/discord_bot_curaga/views/retention_confirmation.py` (new)
- Keep confirmation UI isolated and reusable.

### `src/discord_bot_curaga/bot.py`
- Register the retention cog.

### `src/discord_bot_curaga/_tests/test_config.py`
- Cover env parsing.

### `src/discord_bot_curaga/cogs/_tests/test_retention.py` (new)
- Cover permissions, dry-run, pinned/thread behavior, and purge edge cases.

### `README.md`
- Document the new env vars and retention behavior.
