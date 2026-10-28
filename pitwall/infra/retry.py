"""Retry with exponential backoff and jitter for transient failures."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """All retry attempts have been exhausted."""


async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *args: object,
    max_retries: int = 3,
    base_delay_sec: float = 1.0,
    max_delay_sec: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: Sequence[type[Exception]] = (Exception,),
    **kwargs: object,
) -> T:
    """Call ``fn(*args, **kwargs)`` with retry on transient errors.

    Backoff formula: ``min(base * 2^attempt, max_delay)``, optionally
    multiplied by uniform jitter in ``[0.5, 1.5)``.

    Args:
        fn: The async callable to invoke.
        max_retries: How many times to retry after the initial attempt.
        base_delay_sec: Starting delay before first retry.
        max_delay_sec: Upper bound on delay between retries.
        jitter: Whether to add randomised jitter to the delay.
        retryable_exceptions: Exception types considered transient.

    Returns:
        The return value of ``fn`` on the first successful call.

    Raises:
        RetryExhausted: If all attempts fail.  The ``__cause__`` is the
            last exception raised by ``fn``.
    """
    last_exc: Exception | None = None
    retryable = tuple(retryable_exceptions)

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = min(base_delay_sec * (2**attempt), max_delay_sec)
            if jitter:
                delay *= 0.5 + random.random()  # noqa: S311
            await asyncio.sleep(delay)

    raise RetryExhausted(
        f"Failed after {max_retries + 1} attempts"
    ) from last_exc
