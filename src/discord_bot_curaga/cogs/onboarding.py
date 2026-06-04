from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_curaga.context import AppContext
from discord_bot_curaga.utils.discord_types import (
    ChannelWithDeleteMessages,
)
from discord_bot_curaga.utils.iter import chunked
from discord_bot_curaga.views.approval_request import ApprovalRequestView


class OnboardingCog(commands.Cog):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self._views_registered = False

    @property
    def bot(self) -> commands.Bot:
        return self.ctx.bot

    @property
    def client(self):
        return self.ctx.client

    @property
    def config(self):
        return self.ctx.config

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self.client.get_guild()
            await self.client.get_channel_approval()
            await self.client.get_role_for_approved()
            await self.client.get_role_for_admin()
        except RuntimeError as e:
            self.ctx.logger.warning(
                f"Startup failed: {e}", extra={"skip_discord": True}
            )
            await self.bot.close()
            return

        if not self._views_registered:
            self.bot.add_view(self._approval_view())
            self._views_registered = True

        await self._log(f"Hello world! {self.bot.user} is running...")

    async def _log(self, message: str):
        self.ctx.logger.info(message)

    @app_commands.command(
        name="purge_approval_requests",
        description="Delete resolved approval requests older than a certain age from the approval channel.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        minutes_old="Only delete resolved approval requests older than this many minutes (default: 10)."
    )
    async def purge_approval_requests(
        self, interaction: discord.Interaction, minutes_old: int = 10
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

        if minutes_old < 0:
            await interaction.response.send_message(
                "minutes_old must be 0 or greater.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            approval_channel = await self.client.get_channel_approval()
        except RuntimeError as e:
            await interaction.edit_original_response(content=f"[ERROR] {e}")
            return

        if not isinstance(approval_channel, ChannelWithDeleteMessages):
            await interaction.edit_original_response(
                content="[ERROR] Channel is not a text channel."
            )
            return

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes_old)
        deleted_messages: list[discord.Message] = []
        skipped_pending = 0
        messages_iter = approval_channel.history(
            limit=None, oldest_first=True, before=cutoff
        )

        async for message in messages_iter:
            if message.created_at > cutoff:
                continue

            if not self._is_approval_request_message(message):
                continue

            status = self._approval_request_status(message)
            if status is None:
                skipped_pending += 1
                continue

            deleted_messages.append(message)

        deleted_count = len(deleted_messages)

        if not deleted_messages:
            await interaction.edit_original_response(
                content=("No messages found to delete.")
            )
        elif self.config.dry_run:
            await interaction.edit_original_response(
                content=(
                    f"Dry run complete. Would delete {deleted_count} resolved approval request(s) older than {minutes_old} minute(s)."
                )
            )
        else:
            await self._delete_approval_requests(approval_channel, deleted_messages)
            await interaction.edit_original_response(
                content=(
                    f"Purged {deleted_count} resolved approval request(s) older than {minutes_old} minute(s)."
                )
            )

        await self._log(
            f"{interaction.user} purged {deleted_count} approval request(s); skipped {skipped_pending} pending request(s)."
        )

    async def _has_admin_role(self, member: discord.Member) -> bool:
        admin_role = await self.client.get_role_for_admin()
        return admin_role in member.roles

    def _is_approval_request_message(self, message: discord.Message) -> bool:
        if self.bot.user is not None:
            if getattr(message.author, "id", None) != self.bot.user.id:
                return False
        elif not getattr(message.author, "bot", False):
            return False

        if not message.embeds:
            return False

        embed = message.embeds[0]
        if embed.title != "Approval Request":
            return False

        footer_text = embed.footer.text or ""
        return footer_text.startswith("member_id:")

    def _approval_request_status(self, message: discord.Message) -> bool | None:
        if not message.embeds:
            return None

        for field in message.embeds[0].fields:
            if field.name != "Status":
                continue

            status_value = field.value.strip().lower() if field.value else ""
            if status_value.startswith("approved"):
                return True
            if status_value.startswith("rejected"):
                return False
            return None

        return None

    async def _delete_approval_requests(
        self, channel: ChannelWithDeleteMessages, messages: list[discord.Message]
    ):
        for batch in chunked(messages, 100):
            try:
                await channel.delete_messages(batch)
            except discord.Forbidden:
                await self._log(
                    "[WARN] Missing permissions to bulk delete approval requests"
                )
                await self._delete_approval_requests_individually(batch)
            except discord.HTTPException as e:
                await self._log(f"[WARN] Failed to bulk delete approval requests: {e}")
                await self._delete_approval_requests_individually(batch)

    async def _delete_approval_requests_individually(
        self, messages: list[discord.Message]
    ):
        for message in messages:
            try:
                await message.delete()
            except discord.Forbidden:
                await self._log(
                    f"[WARN] Missing permissions to delete approval request {message.id}"
                )
            except discord.HTTPException as e:
                await self._log(
                    f"[WARN] Failed to delete approval request {message.id}: {e}"
                )

    async def on_rules_acknowledge(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This action can only be used in a server.", ephemeral=True
            )
            return

        if interaction.guild_id != self.config.guild_id:
            await interaction.response.send_message(
                "This action can only be used in the configured server.",
                ephemeral=True,
            )
            return

        if await self._member_has_approved_role(interaction.user):
            await interaction.response.send_message(
                "Thanks for accepting the rules again - you already have access.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Thanks for accepting the rules! We'll let the mods know you're here.",
            ephemeral=True,
        )

        try:
            await self._post_approval_request(interaction.user)
        except Exception as e:
            self.ctx.logger.warning(
                f"Failed to create approval request: {e}", extra={"skip_discord": True}
            )
            await interaction.followup.send(
                "I couldn't create the approval request right now. Please ask for help in #git-help.",
                ephemeral=True,
            )
            return

    async def _member_has_approved_role(self, member: discord.Member) -> bool:
        approved_role = await self.client.get_role_for_approved()
        if approved_role in member.roles:
            await self._log(
                f"Ignoring rules acknowledgement from {member.display_name}; already has {approved_role.name}."
            )
            return True
        return False

    async def _post_approval_request(self, member: discord.Member):
        channel = await self.client.get_channel_approval()

        embed = discord.Embed(
            title="Approval Request",
            description=f"{member.mention} acknowledged the server rules.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Member", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Status", value="Pending ⏳", inline=False)
        embed.set_footer(text=f"member_id:{member.id}")

        await channel.send(embed=embed, view=self._approval_view())

        await self._log(f"⏳ Created approval request for {member.display_name}")

    async def _on_approval_approve(self, interaction: discord.Interaction):
        await self._handle_approval_action(interaction, approved=True)

    async def _on_approval_reject(self, interaction: discord.Interaction):
        await self._handle_approval_action(interaction, approved=False)

    async def _handle_approval_action(
        self, interaction: discord.Interaction, approved: bool
    ):
        if not isinstance(interaction.user, discord.Member):
            return

        action = "approve" if approved else "reject"
        permission_message = f"You do not have permission to {action} requests."

        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(permission_message, ephemeral=True)
            return

        member = await self._get_requested_member(interaction)
        if member is None:
            return

        if approved:
            role = await self.client.get_role_for_approved()

            if role not in member.roles and not self.config.dry_run:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "[WARN] Missing permissions to assign role.", ephemeral=True
                    )
                    return
                except discord.HTTPException as e:
                    await interaction.response.send_message(
                        f"[WARN] Failed to assign role: {e}", ephemeral=True
                    )
                    return

            await self._log(
                f"{interaction.user} approved {member.display_name}; granted {role.name}"
            )
        else:
            await self._log(f"{interaction.user} rejected {member.display_name}")

        await self._finish_approval_message(interaction, approved=approved)

    async def _finish_approval_message(
        self, interaction: discord.Interaction, approved: bool
    ):
        if not interaction.message:
            return

        status_text = (
            f"Approved ✅ by {interaction.user.mention}"
            if approved
            else f"Rejected ❌ by {interaction.user.mention}"
        )
        color = discord.Color.green() if approved else discord.Color.red()

        embed = (
            interaction.message.embeds[0]
            if interaction.message.embeds
            else discord.Embed()
        )
        embed.color = color

        if len(embed.fields) >= 2:
            embed.set_field_at(1, name="Status", value=status_text, inline=False)
        else:
            embed.add_field(name="Status", value=status_text, inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

    async def _get_requested_member(
        self, interaction: discord.Interaction
    ) -> discord.Member | None:
        member_id = self._get_member_id_from_interaction(interaction)
        if member_id is None:
            await interaction.response.send_message(
                "[WARN] Could not determine requested member for this approval.",
                ephemeral=True,
            )
            return None

        member = await self.client.get_guild_member(member_id)
        if member is None:
            await interaction.response.send_message(
                f"[WARN] Could not find member with id {member_id}.", ephemeral=True
            )
            return None

        return member

    def _approval_view(self) -> ApprovalRequestView:
        return ApprovalRequestView(
            disabled=False,
            on_approve=self._on_approval_approve,
            on_reject=self._on_approval_reject,
        )

    def _get_member_id_from_interaction(self, interaction: discord.Interaction):
        if not interaction.message or not interaction.message.embeds:
            return None

        footer_text = interaction.message.embeds[0].footer.text or ""
        if not footer_text.startswith("member_id:"):
            return None

        try:
            return int(footer_text.split(":", 1)[1])
        except ValueError:
            return None


async def setup(bot: commands.Bot, ctx: AppContext):
    await bot.add_cog(OnboardingCog(ctx))
