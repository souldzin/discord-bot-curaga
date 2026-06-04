# Plan: Server Rules

**Scope:** Add an admin-only slash command to sync the server rules channel from one or more source messages.

## Goal

Allow admins/mods to update the rules channel by copying the content of existing messages into the configured rules channel.

## Proposed command

```text
/rules_sync message_ids:<string>
```

- `message_ids` is required.
- It should accept one or more source message IDs (implementation may use a comma-separated string or equivalent supported slash-command option).

## Permissions

- Only users with `ROLE_ID_ADMIN` may use the command.
- Add a new setting: `ROLE_ID_ADMIN`.

## Behavior

1. The bot reads all source messages first.
2. If any source message cannot be fetched, the command fails immediately and **no changes** are made to the rules channel.
3. If all messages are readable:
   1. Post a temporary message in `CHANNEL_ID_RULES` saying the rules are being updated.
   2. Delete all messages in `CHANNEL_ID_RULES`.
   3. Repost the content of each source message in order.
   4. Post a final rules acknowledgement message, preferably as an embed with a persistent button (e.g. `I Agree`).

## Rules channel lookup

The onboarding flow should support both:

- the existing `MESSAGE_ID_RULES` reaction path
- a rules acknowledgement message in `CHANNEL_ID_RULES` that uses the persistent acknowledgement button

This is a migration path. Eventually `MESSAGE_ID_RULES` can be removed once the button-based flow is fully established.

## Notes

- The rules channel is assumed to be bot-controlled and locked down, so deleting all messages there is acceptable.
- The command copies content only; embeds/attachments are not required.
- The final acknowledgement should be a persistent interaction message (button-based), ideally with an embed for formatting.
- If `DRY_RUN` is enabled, the command should log the full sequence of actions it would perform and make no changes to the rules channel.

## Implementation plan

- [ ] `src/discord_bot_curaga/config.py`
  - [ ] Add `channel_id_rules: int` and `role_id_admin: int` to `AppConfig`
  - [ ] Load `CHANNEL_ID_RULES` and `ROLE_ID_ADMIN` from env
- [ ] `src/discord_bot_curaga/utils/discord_client.py`
  - [ ] Add `get_channel_rules()` helper (same pattern as `get_channel_approval()`)
  - [ ] Add a helper to fetch a message by channel + message ID so the sync command can fail fast before mutating anything
- [ ] `src/discord_bot_curaga/cogs/server_rules.py` (new)
  - [ ] Add `/rules_sync` slash command with required `message_ids`
  - [ ] Parse `message_ids` into a list of ints
  - [ ] Check the invoking member has `ROLE_ID_ADMIN`
  - [ ] Fetch every source message first
  - [ ] If any fetch fails, respond with an error and stop
  - [ ] If all fetch succeed, post the temporary "updating" message in `CHANNEL_ID_RULES`
  - [ ] Purge the rules channel
  - [ ] Repost each source message's content in order
  - [ ] Post the final acknowledgement embed/button message
- [ ] `src/discord_bot_curaga/cogs/onboarding.py`
  - [ ] Keep the current `MESSAGE_ID_RULES` reaction path working during migration
  - [ ] Add a new button-click hook for the rules acknowledgement message in `CHANNEL_ID_RULES`
  - [ ] Prefer the channel-based rules acknowledgement once present
- [ ] `src/discord_bot_curaga/views/` (new or existing)
  - [ ] Add a persistent acknowledgement button view
  - [ ] Make the button trigger the onboarding approval workflow
- [ ] `src/discord_bot_curaga/bot.py`
  - [ ] Load the new `server_rules` cog in `setup_hook`
  - [ ] Add slash-command syncing if needed for the app command tree
- [ ] Tests
  - [ ] Add config tests for new env vars
  - [ ] Add command tests for permission gating and fail-fast fetch behavior
  - [ ] Add onboarding tests for both rules-message lookup modes
