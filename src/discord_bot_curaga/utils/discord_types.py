from types import CoroutineType
from typing import Protocol

import discord


class InteractionCallable(Protocol):
    def __call__(
        self, interaction: discord.Interaction
    ) -> CoroutineType[None, None, None]: ...
