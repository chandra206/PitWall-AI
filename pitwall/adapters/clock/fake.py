"""Adapter: fake clock — deterministic time for tests.

Time does not advance unless explicitly ticked by the test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pitwall.ports.clock import Clock


class FakeClock(Clock):
    """Deterministic clock for testing — time advances only on ``tick()``."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        """Return the current fake time."""
        return self._now

    def tick(self, seconds: float = 1.0) -> datetime:
        """Advance time by *seconds* and return the new time."""
        self._now += timedelta(seconds=seconds)
        return self._now

    def set(self, dt: datetime) -> None:
        """Jump to an exact time."""
        self._now = dt
