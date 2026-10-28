"""Port: MetricsCollector — counters, gauges, and timings for the efficiency panel."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MetricsCollector(ABC):
    """Abstract collector for operational metrics.

    Exposes counters, gauges, and timing data through a single interface
    that the efficiency panel (or any monitoring adapter) can consume.
    """

    @abstractmethod
    def increment(self, name: str, value: int = 1, **tags: str) -> None:
        """Increment a counter metric."""
        ...

    @abstractmethod
    def gauge(self, name: str, value: float, **tags: str) -> None:
        """Set an absolute gauge value."""
        ...

    @abstractmethod
    def record_timing(self, name: str, duration_ms: float, **tags: str) -> None:
        """Record a timing measurement in milliseconds."""
        ...

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time snapshot of all metrics.

        The returned dict is a serializable representation suitable for
        JSON output or dashboard rendering.
        """
        ...
