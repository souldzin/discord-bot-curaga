from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar, cast

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


def async_cache(fn: F) -> F:
    cache: dict[tuple[Any, ...], asyncio.Task[Any]] = {}
    lock = asyncio.Lock()
    marker = object()

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
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
    return cast(F, wrapper)
