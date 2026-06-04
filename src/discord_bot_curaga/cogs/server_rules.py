from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_curaga.cogs.onboarding import OnboardingCog
from discord_bot_curaga.context import AppContext
from discord_bot_curaga.utils.parse_args import parse_comma_separated_ids
from discord_bot_curaga.views.rules_acknowledgement import RulesAcknowledgementView


class ServerRulesCog(commands.Cog):
    _view_registered: bool

    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._view_registered = False

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.client.get_channel_rules()
            await self.client.get_role_for_admin()
        except RuntimeError as e:
            self.ctx.logger.warning(
                f"Startup failed: {e}", extra={"skip_discord": True}
            )
            await self.bot.close()
            return

        if not self._view_registered:
            self.bot.add_view(self._rules_ack_view())
            self._view_registered = True

    @property
    def bot(self) -> commands.Bot:
        return self.ctx.bot

    @property
    def client(self):
        return self.ctx.client

    @property
    def config(self):
        return self.ctx.config

    @app_commands.command(
        name="rules_sync",
        description="Sync the rules channel from one or more source messages.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        message_ids="Comma-separated list of source message IDs to copy in order."
    )
    async def curaga_rules_sync(
        self, interaction: discord.Interaction, message_ids: str
    ):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        try:
            has_admin_role = await self._has_admin_role(interaction.user)
        except RuntimeError as e:
            await interaction.response.send_message(f"[ERROR] {e}", ephemeral=True)
            return

        if not has_admin_role:
            await interaction.response.send_message(
                "You do not have permission to run this command.", ephemeral=True
            )
            return

        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                "This command must be used in a text channel or thread.",
                ephemeral=True,
            )
            return

        source_message_ids = self._parse_message_ids(message_ids)
        if not source_message_ids:
            await interaction.response.send_message(
                "Please provide at least one valid message ID.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        source_messages = []
        for source_message_id in source_message_ids:
            message = await self.client.fetch_message(
                interaction.channel.id, source_message_id
            )
            if message is None:
                await interaction.edit_original_response(
                    content=(
                        f"[ERROR] Could not fetch source message `{source_message_id}`. "
                        "No changes were made."
                    )
                )
                return
            source_messages.append(message)

        try:
            rules_channel = await self.client.get_channel_rules()
        except RuntimeError as e:
            await interaction.edit_original_response(content=f"[ERROR] {e}")
            return

        if self.config.dry_run:
            await self._log_dry_run(rules_channel.id, source_messages)
            await interaction.edit_original_response(
                content="Dry run complete. No changes were made."
            )
            return

        try:
            await rules_channel.send("Updating server rules...")
            await rules_channel.purge(limit=None)

            for source_message in source_messages:
                content = source_message.content or "\u200b"
                await rules_channel.send(content)

            await rules_channel.send(
                embed=self._rules_acknowledgement_embed(),
                view=self._rules_ack_view(),
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                content="[ERROR] Missing permissions to update the rules channel."
            )
            return
        except discord.HTTPException as e:
            await interaction.edit_original_response(
                content=f"[ERROR] Failed to update the rules channel: {e}"
            )
            return

        await interaction.edit_original_response(content="Rules channel updated.")
        await self._log(
            f"{interaction.user} synced the rules channel with {len(source_messages)} source message(s)."
        )

    async def _has_admin_role(self, member: discord.Member) -> bool:
        admin_role = await self.client.get_role_for_admin()
        return admin_role in member.roles

    def _parse_message_ids(self, message_ids: str) -> list[int]:
        return parse_comma_separated_ids(message_ids)

    async def _log(self, message: str):
        self.ctx.logger.info(message)

    def _rules_acknowledgement_embed(self) -> discord.Embed:
        return discord.Embed(
            title="Server Rule Agreement",
            description="I have read, understand, and will adhere to the above server rules and guidelines.",
            color=discord.Color.blurple(),
        )

    def _rules_ack_view(self) -> RulesAcknowledgementView:
        onboarding_cog = self.bot.get_cog("OnboardingCog")
        if onboarding_cog is None or not isinstance(onboarding_cog, OnboardingCog):
            raise RuntimeError("OnboardingCog not loaded")

        return RulesAcknowledgementView(
            on_acknowledge=onboarding_cog.on_rules_acknowledge
        )

    async def _log_dry_run(self, rules_channel_id: int, source_messages):
        await self._log(f"DRY RUN: would update rules channel {rules_channel_id}")
        await self._log(
            'DRY RUN: would post temporary message "Updating server rules..."'
        )
        await self._log(
            f"DRY RUN: would purge all messages in rules channel {rules_channel_id}"
        )

        for source_message in source_messages:
            content = source_message.content or "\u200b"
            await self._log(
                f"DRY RUN: would repost source message {source_message.id}: {content!r}"
            )

        await self._log(
            "DRY RUN: would post acknowledgement embed with persistent I Agree button"
        )
        await self._log("DRY RUN complete: no changes were made.")


async def setup(bot: commands.Bot, ctx: AppContext):
    await bot.add_cog(ServerRulesCog(ctx))
