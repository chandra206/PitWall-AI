"""Three-layer watchdog — monitors pipeline health and data freshness.

Layer 1 — **Telemetry liveness**: alerts if no telemetry frame arrives
           within ``telemetry_timeout_sec``.
Layer 2 — **Pipeline throughput**: alerts if an alert enters the pipeline
           but no radio call is produced within ``pipeline_timeout_sec``.
Layer 3 — **Periodic health check**: emits a metrics snapshot every
           ``health_check_interval_sec`` for the efficiency panel.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from pitwall.domain.enums import AlertSeverity, PipelineStage
from pitwall.domain.events import (
    AlertRaised,
    RadioCallReady,
    TelemetryReceived,
)
from pitwall.domain.models import RadioCall
from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector


class WatchdogService:
    """Three-layer watchdog that monitors the real-time pipeline.

    Subscribes to key events and raises internal alerts if SLAs are
    breached (stale telemetry, stuck pipeline, etc.).
    """

    def __init__(
        self,
        clock: Clock,
        logger: StructuredLogger,
        metrics: MetricsCollector,
        event_bus: EventBus,
        *,
        telemetry_timeout_sec: float = 5.0,
        pipeline_timeout_sec: float = 60.0,
        health_check_interval_sec: float = 10.0,
    ) -> None:
        self._clock = clock
        self._logger = logger
        self._metrics = metrics
        self._bus = event_bus
        self._telemetry_timeout = telemetry_timeout_sec
        self._pipeline_timeout = pipeline_timeout_sec
        self._health_interval = health_check_interval_sec

        self._last_telemetry_time: datetime | None = None
        self._inflight_alerts: dict[str, datetime] = {}  # correlation_id → entry_time
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []

    # ── Event handlers ───────────────────────────────────────────────

    async def on_telemetry(self, event: TelemetryReceived) -> None:
        """Layer 1: record that telemetry is alive."""
        self._last_telemetry_time = self._clock.now()
        self._metrics.gauge(
            "watchdog.telemetry_age_sec", 0.0
        )

    async def on_alert_raised(self, event: AlertRaised) -> None:
        """Layer 2: track in-flight alert for pipeline throughput."""
        key = str(event.correlation_id)
        self._inflight_alerts[key] = self._clock.now()

    async def on_radio_ready(self, event: RadioCallReady) -> None:
        """Layer 2: alert completed the pipeline — remove from tracking."""
        key = str(event.correlation_id)
        entry_time = self._inflight_alerts.pop(key, None)
        if entry_time is not None:
            elapsed_ms = (self._clock.now() - entry_time).total_seconds() * 1000
            self._metrics.record_timing("watchdog.pipeline_latency_ms", elapsed_ms)

    # ── Background monitors ──────────────────────────────────────────

    async def start(self) -> None:
        """Start the watchdog background loops."""
        self._running = True
        self._tasks.append(asyncio.create_task(self._check_telemetry_loop()))
        self._tasks.append(asyncio.create_task(self._check_pipeline_loop()))
        self._tasks.append(asyncio.create_task(self._health_check_loop()))
        self._logger.info("Watchdog started")

    async def stop(self) -> None:
        """Stop all watchdog background loops cleanly."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._logger.info("Watchdog stopped")

    async def _check_telemetry_loop(self) -> None:
        """Layer 1: periodically verify telemetry freshness."""
        while self._running:
            await asyncio.sleep(self._telemetry_timeout)
            if self._last_telemetry_time is None:
                continue
            age = (self._clock.now() - self._last_telemetry_time).total_seconds()
            self._metrics.gauge("watchdog.telemetry_age_sec", age)
            if age > self._telemetry_timeout:
                self._logger.warning(
                    f"Telemetry stale: no data for {age:.1f}s "
                    f"(threshold: {self._telemetry_timeout}s)",
                )
                self._metrics.increment("watchdog.telemetry_stale_events")

    async def _check_pipeline_loop(self) -> None:
        """Layer 2: detect alerts stuck in the pipeline."""
        while self._running:
            await asyncio.sleep(self._pipeline_timeout / 2)
            now = self._clock.now()
            stuck: list[str] = []
            for cid, entry_time in list(self._inflight_alerts.items()):
                elapsed = (now - entry_time).total_seconds()
                if elapsed > self._pipeline_timeout:
                    stuck.append(cid)
                    self._logger.warning(
                        f"Alert {cid[:8]}… stuck in pipeline for {elapsed:.1f}s",
                        correlation_id=None,
                    )
                    self._metrics.increment("watchdog.pipeline_stuck_events")
            # Evict stuck alerts so we don't re-warn indefinitely.
            for cid in stuck:
                self._inflight_alerts.pop(cid, None)

    async def _health_check_loop(self) -> None:
        """Layer 3: emit periodic health/metrics snapshot."""
        while self._running:
            await asyncio.sleep(self._health_interval)
            snapshot = self._metrics.snapshot()
            self._logger.info(
                "Health check",
                metrics=snapshot,
            )
