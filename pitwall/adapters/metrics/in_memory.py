"""Adapter: in-memory metrics collector for the efficiency panel.

Stores counters, gauges, and timing data in plain dicts.
Suitable for single-process deployments and testing.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from pitwall.ports.metrics import MetricsCollector


class InMemoryMetricsCollector(MetricsCollector):
    """Thread-safe (GIL-protected) in-memory metrics store.

    Provides ``snapshot()`` for the efficiency panel or any monitoring
    adapter to consume the current state of all metrics.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1, **tags: str) -> None:
        """Increment a counter by *value*."""
        key = self._make_key(name, tags)
        self._counters[key] += value

    def gauge(self, name: str, value: float, **tags: str) -> None:
        """Set a gauge to an absolute *value*."""
        key = self._make_key(name, tags)
        self._gauges[key] = value

    def record_timing(self, name: str, duration_ms: float, **tags: str) -> None:
        """Record a timing sample in milliseconds."""
        key = self._make_key(name, tags)
        self._timings[key].append(duration_ms)

    def snapshot(self) -> dict[str, Any]:
        """Return all metrics as a serializable dict."""
        timing_stats: dict[str, dict[str, float]] = {}
        for key, samples in self._timings.items():
            if samples:
                sorted_s = sorted(samples)
                timing_stats[key] = {
                    "count": len(sorted_s),
                    "min": sorted_s[0],
                    "max": sorted_s[-1],
                    "mean": sum(sorted_s) / len(sorted_s),
                    "p50": sorted_s[len(sorted_s) // 2],
                    "p99": sorted_s[int(len(sorted_s) * 0.99)],
                }

        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timings": timing_stats,
        }

    @staticmethod
    def _make_key(name: str, tags: dict[str, str]) -> str:
        """Build a metric key including any tags."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"
