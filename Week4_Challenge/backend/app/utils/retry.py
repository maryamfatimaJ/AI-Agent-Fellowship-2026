"""Reusable async retry decorator with exponential backoff.

Used by tools and outbound HTTP calls to satisfy the failure-handling
requirement (timeouts, transient API failures) without duplicating backoff
logic across every tool module.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.config.logging_config import get_logger

_T = TypeVar("_T")
logger = get_logger("utils.retry")


def async_retry(
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    max_delay_seconds: float = 8.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[_T]]], Callable[..., Awaitable[_T]]]:
    def decorator(func: Callable[..., Awaitable[_T]]) -> Callable[..., Awaitable[_T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> _T:
            attempt = 0
            delay = base_delay_seconds
            last_exc: BaseException | None = None

            while attempt < max_attempts:
                attempt += 1
                try:
                    return await func(*args, **kwargs)
                except retry_on as exc:  # noqa: PERF203 - retry loop is intentional
                    last_exc = exc
                    logger.warning(
                        "retry.attempt_failed",
                        function=func.__name__,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(exc),
                    )
                    if attempt >= max_attempts:
                        break
                    await asyncio.sleep(min(delay, max_delay_seconds))
                    delay *= 2

            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
