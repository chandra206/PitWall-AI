"""Port: Clock — injectable time source for deterministic testing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Abstract clock for all time-dependent operations.

    Inject this instead of calling ``datetime.utcnow()`` directly so that
    tests can use a ``FakeClock`` with fully deterministic time.
    """

    @abstractmethod
    def now(self) -> datetime:
        """Return the current UTC time."""
        ...
