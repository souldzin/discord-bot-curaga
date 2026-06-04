import discord

from discord_bot_curaga.utils.discord_types import InteractionCallable


class RetentionConfirmationView(discord.ui.View):
    CONFIRM_ID = "retention:confirm"
    CANCEL_ID = "retention:cancel"

    def __init__(
        self,
        disabled: bool = False,
        on_confirm: InteractionCallable | None = None,
        on_cancel: InteractionCallable | None = None,
    ):
        super().__init__(timeout=None)

        confirm_button = discord.ui.Button(
            label="Yes",
            style=discord.ButtonStyle.danger,
            emoji="⚠️",
            custom_id=self.CONFIRM_ID,
            disabled=disabled,
        )
        cancel_button = discord.ui.Button(
            label="No",
            style=discord.ButtonStyle.secondary,
            emoji="✋",
            custom_id=self.CANCEL_ID,
            disabled=disabled,
        )

        if on_confirm:
            confirm_button.callback = on_confirm
        if on_cancel:
            cancel_button.callback = on_cancel

        self.add_item(confirm_button)
        self.add_item(cancel_button)

    def set_disabled(self, disabled: bool):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = disabled
