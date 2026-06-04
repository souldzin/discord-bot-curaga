import discord

from discord_bot_curaga.utils.discord_types import InteractionCallable


class RulesAcknowledgementView(discord.ui.View):
    ACKNOWLEDGE_ID = "rules:acknowledge"

    def __init__(
        self,
        disabled: bool = False,
        on_acknowledge: InteractionCallable | None = None,
    ):
        super().__init__(timeout=None)

        acknowledge_button = discord.ui.Button(
            label="I Agree",
            style=discord.ButtonStyle.success,
            emoji="👍",
            custom_id=self.ACKNOWLEDGE_ID,
            disabled=disabled,
        )

        if on_acknowledge:
            acknowledge_button.callback = on_acknowledge

        self.add_item(acknowledge_button)
