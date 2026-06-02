import sys
import traceback
from typing import Awaitable, Callable

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from .config import BotConfig

# region: constants - - - - - - - - - - - - - - - - - - - -
PREFIX_DRY_RUN = "[DRY RUN]"


# region: view - - - - - - - - - - - - - - - - - - - -
class ApprovalRequestView(discord.ui.View):
    APPROVE_ID = "approval:approve"
    REJECT_ID = "approval:reject"

    def __init__(
        self,
        disabled: bool = False,
        on_approve: Callable[[discord.Interaction], Awaitable[None]] | None = None,
        on_reject: Callable[[discord.Interaction], Awaitable[None]] | None = None,
    ):
        super().__init__(timeout=None)

        approve_button = discord.ui.Button(
            label="Approve",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id=self.APPROVE_ID,
            disabled=disabled,
        )
        reject_button = discord.ui.Button(
            label="Reject",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id=self.REJECT_ID,
            disabled=disabled,
        )

        if on_approve:
            approve_button.callback = on_approve

        if on_reject:
            reject_button.callback = on_reject

        self.add_item(approve_button)
        self.add_item(reject_button)


class BotApp:
    _config: BotConfig

    def __init__(self, config: BotConfig):
        self._config = config

        self._bot = self._create_bot()
        self._guild = None
        self._role_approved = None
        self._channel_log = None
        self._channel_approval = None
        self._is_ready = False

    def _warn(self, message: str):
        print(f"[WARN] {message}")

    def run(self):
        self._setup_events()

        self._bot.run(self._config.token)

    def _setup_events(self):
        @self._bot.event
        async def on_ready():
            await self._on_ready()

        @self._bot.event
        async def on_raw_reaction_add(payload):
            await self._on_raw_reaction_add(payload)

        @self._bot.event
        async def on_error(event, *args, **kwargs):
            await self._on_error(event)

    # region: tasks - - - - - - - - - - - - - - - - - - - -
    @tasks.loop(minutes=10)
    async def _task_heartbeat(self):
        try:
            await self._log("💓 heartbeat")
        except Exception as e:
            self._warn(f"Heartbeat task failed: {e}")

    # region: handlers - - - - - - - - - - - - - - - - - - - -
    async def _on_ready(self):
        try:
            await self._prime_cache()
        except RuntimeError as e:
            self._warn(f"Startup failed: {e}")
            await self._bot.close()
            return

        if not self._is_ready:
            self._bot.add_view(
                ApprovalRequestView(
                    disabled=False,
                    on_approve=self._on_approval_approve,
                    on_reject=self._on_approval_reject,
                )
            )

        if not self._task_heartbeat.is_running():
            self._task_heartbeat.start()

        self._is_ready = True

        await self._log(f"Hello world! {self._bot.user} is running...")

    async def _on_raw_reaction_add(self, payload):
        # STEP: Make sure this is the reaction we're looking for
        if self._bot.user and payload.user_id == self._bot.user.id:
            return

        if payload.message_id != self._config.message_id_rules:
            return

        if str(payload.emoji) != self._config.approval_emoji:
            return

        if payload.guild_id != self._config.guild_id:
            return

        member = await self._get_guild_member(payload.user_id)
        if member is None:
            return

        approved_role = await self._get_role_approved()
        if approved_role in member.roles:
            await self._log(
                f"Ignoring rules reaction from {member.display_name}; already has {approved_role.name}."
            )
            return

        # STEP: We are ready to start processing the approval request!
        try:
            await member.send(
                "Thanks for accepting the rules! A moderator will review your request shortly."
            )
        except discord.Forbidden:
            await self._log(f"[WARN] Could not DM {member.display_name} (DMs closed).")

        await self._post_approval_request(member)

    async def _on_error(self, event):
        error = traceback.format_exc()
        print(error)

        error_type = "UnknownError"
        exception = sys.exc_info()[1]
        exc = (
            traceback.TracebackException.from_exception(exception)
            if exception
            else None
        )
        if exc is not None:
            error_type = exc.exc_type.__name__ if exc.exc_type else error_type
            print("".join(exc.format_exception_only()).strip())

        await self._log(f"[WARN] Unhandled error in `{event}`: `{error_type}`")

    async def _log(self, message: str):
        if self._config.dry_run and not message.startswith(PREFIX_DRY_RUN):
            message = f"{PREFIX_DRY_RUN} {message}"

        print(message)

        log_channel = await self._get_channel_log()
        if log_channel:
            await log_channel.send(message)

    async def _post_approval_request(self, member: discord.Member):
        channel = await self._get_channel_approval()

        embed = discord.Embed(
            title="Approval Request",
            description=f"{member.mention} reacted with {self._config.approval_emoji} to the rules message.",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Member", value=f"{member} (`{member.id}`)", inline=False)
        embed.add_field(name="Status", value="Pending ⏳", inline=False)
        embed.set_footer(text=f"member_id:{member.id}")

        await channel.send(
            embed=embed,
            view=ApprovalRequestView(
                disabled=False,
                on_approve=self._on_approval_approve,
                on_reject=self._on_approval_reject,
            ),
        )

        await self._log(f"⏳ Created approval request for {member.display_name}")

    async def _on_approval_approve(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "You do not have permission to approve requests.", ephemeral=True
            )
            return

        member_id = self._get_member_id_from_interaction(interaction)
        if member_id is None:
            await interaction.response.send_message(
                "[WARN] Could not determine requested member for this approval.",
                ephemeral=True,
            )
            return

        member = await self._get_guild_member(member_id)
        if member is None:
            await interaction.response.send_message(
                f"[WARN] Could not find member with id {member_id}.", ephemeral=True
            )
            return

        role = await self._get_role_approved()

        if role not in member.roles and not self._config.dry_run:
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
        await self._finish_approval_message(interaction, approved=True)

    async def _on_approval_reject(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "You do not have permission to reject requests.", ephemeral=True
            )
            return

        member_id = self._get_member_id_from_interaction(interaction)
        if member_id is None:
            await interaction.response.send_message(
                "[WARN] Could not determine requested member for this approval.",
                ephemeral=True,
            )
            return

        member = await self._get_guild_member(member_id)
        if member is None:
            await interaction.response.send_message(
                f"[WARN] Could not find member with id {member_id}.", ephemeral=True
            )
            return

        await self._log(f"{interaction.user} rejected {member.display_name}")
        await self._finish_approval_message(interaction, approved=False)

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

        await interaction.response.edit_message(
            embed=embed,
            view=None,
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

    def _create_bot(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.reactions = True

        return commands.Bot(command_prefix="!", intents=intents)

    async def _prime_cache(self):
        await self._get_guild()
        await self._get_channel_log()
        await self._get_channel_approval()
        await self._get_role_approved()

    async def _get_guild(self):
        if self._guild is not None:
            return self._guild

        guild_id = self._config.guild_id
        self._guild = self._bot.get_guild(guild_id)
        if self._guild is None:
            self._warn(f"Required guild not found: {guild_id}")
            raise RuntimeError(f"Required guild not found: {guild_id}")

        return self._guild

    async def _get_role_approved(self):
        if self._role_approved is not None:
            return self._role_approved

        guild = await self._get_guild()

        id = self._config.role_id_approved
        self._role_approved = guild.get_role(id)
        if self._role_approved is None:
            self._warn(f"Required role not found: {id}")
            raise RuntimeError(f"Required role not found: {id}")

        return self._role_approved

    async def _get_guild_member(self, user_id: int):
        guild = await self._get_guild()

        member = guild.get_member(user_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(user_id)
        except discord.NotFound:
            await self._log(f"[WARN] Could not find member with id {user_id}")
        except discord.Forbidden:
            await self._log(
                f"[WARN] Missing permissions to fetch member with id {user_id}"
            )
        except discord.HTTPException as e:
            await self._log(f"[WARN] Failed to fetch member with id {user_id}: {e}")

        return None

    async def _get_channel_log(self):
        if self._channel_log is not None:
            return self._channel_log

        id = self._config.channel_id_log
        self._channel_log = await self._get_channel(id)
        if self._channel_log is None:
            self._warn(f"Optional log channel not found: {id}")
        return self._channel_log

    async def _get_channel_approval(self):
        if self._channel_approval is not None:
            return self._channel_approval

        id = self._config.channel_id_approval
        self._channel_approval = await self._get_channel(id)
        if self._channel_approval is None:
            self._warn(f"Required approval channel not found: {id}")
            raise RuntimeError(f"Required approval channel not found: {id}")

        return self._channel_approval

    async def _get_channel(self, channel_id: int):
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            channel = await self._bot.fetch_channel(channel_id)
        return channel


# region: main - - - - - - - - - - - - - - - - - - - -
def main():
    load_dotenv()
    config = BotConfig.create_from_env()

    app = BotApp(config)

    app.run()


if __name__ == "__main__":
    main()
