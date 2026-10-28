"""Adapter: system clock — real UTC time."""

from __future__ import annotations

from datetime import datetime, timezone

from pitwall.ports.clock import Clock


class SystemClock(Clock):
    """Clock implementation that returns real UTC wall-clock time."""

    def now(self) -> datetime:
        """Return ``datetime.now(UTC)``."""
        return datetime.now(timezone.utc)
