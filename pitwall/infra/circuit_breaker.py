"""Circuit breaker — prevents cascading failures on external calls.

State machine: CLOSED → (failures ≥ threshold) → OPEN → (timeout expires)
→ HALF_OPEN → (success) → CLOSED  or  (failure) → OPEN.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from typing import Literal

from pitwall.domain.enums import CircuitState


class CircuitBreakerOpen(Exception):
    """Raised when a call is attempted while the circuit is open."""


class CircuitBreaker:
    """Async-safe circuit breaker for wrapping external calls.

    Usage::

        async with breaker:
            result = await some_external_call()

    If the call inside the ``async with`` raises, the breaker counts
    the failure.  After ``failure_threshold`` consecutive failures it
    opens, refusing calls until ``recovery_timeout_sec`` elapses.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_sec: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = timedelta(seconds=recovery_timeout_sec)
        self._half_open_max = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current circuit state (read-only)."""
        return self._state

    async def __aenter__(self) -> CircuitBreaker:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if (
                    self._last_failure_time is not None
                    and datetime.utcnow() - self._last_failure_time
                    >= self._recovery_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit is OPEN; retry after {self._recovery_timeout}"
                    )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max:
                    raise CircuitBreakerOpen(
                        "Circuit is HALF_OPEN and at max probe calls"
                    )
                self._half_open_calls += 1

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> Literal[False]:
        async with self._lock:
            if exc_type is not None:
                self._failure_count += 1
                self._last_failure_time = datetime.utcnow()
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                return False  # re-raise the original exception

            # Success — reset.
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
            self._failure_count = 0
            return False

    def reset(self) -> None:
        """Force-reset to CLOSED (e.g. for tests or manual recovery)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
