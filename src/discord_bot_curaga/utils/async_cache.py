from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def async_cache(fn: Callable[..., Awaitable[T]]):
    cache: dict[tuple[Any, ...], asyncio.Task[T]] = {}
    lock = asyncio.Lock()
    marker = object()

    @wraps(fn)
    async def wrapper(*args, **kwargs) -> T:
        key = args + (marker,) + tuple(sorted(kwargs.items()))

        async with lock:
            task = cache.get(key)
            if task is None:
                task = asyncio.create_task(fn(*args, **kwargs))
                cache[key] = task

        try:
            return await task
        except Exception:
            async with lock:
                if cache.get(key) is task:
                    cache.pop(key, None)
            raise

    def cache_clear():
        cache.clear()

    wrapper.cache_clear = cache_clear  # type: ignore[attr-defined]
    return wrapper
