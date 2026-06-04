from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")


def chunked(items: Sequence[T], size: int) -> Iterator[list[T]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])
