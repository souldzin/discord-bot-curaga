import discord

from discord_bot_curaga.utils.discord_types import InteractionCallable


class ApprovalRequestView(discord.ui.View):
    APPROVE_ID = "approval:approve"
    REJECT_ID = "approval:reject"

    def __init__(
        self,
        disabled: bool = False,
        on_approve: InteractionCallable | None = None,
        on_reject: InteractionCallable | None = None,
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
