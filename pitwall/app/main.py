"""Composition root — the ONLY module that knows concrete adapter classes.

Reads configuration from environment, instantiates all adapters,
wires them into services via constructor injection, subscribes event
handlers, and runs the pipeline with clean startup/shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from collections.abc import AsyncIterator
from uuid import uuid4

from pitwall.adapters.bus.async_bus import AsyncEventBus
from pitwall.adapters.clock.system import SystemClock
from pitwall.adapters.llm.mock import MockLLMClient
from pitwall.adapters.llm.nebius import NebiusLLMClient
from pitwall.adapters.logging.json_logger import JsonStructuredLogger
from pitwall.adapters.metrics.in_memory import InMemoryMetricsCollector
from pitwall.adapters.speech.browser_tts import BrowserTTSSpeechOutput
from pitwall.adapters.speech.null import NullSpeechOutput
from pitwall.adapters.storage.json_file import JsonFileStorage
from pitwall.adapters.telemetry.ac_shared_memory import AssettoCorsaTelemetrySource
from pitwall.adapters.telemetry.csv_replay import CsvReplayTelemetrySource
from pitwall.adapters.telemetry.simulator import SimulatorTelemetrySource
from pitwall.domain.events import (
    AlertRaised,
    AlertTriaged,
    RadioCallReady,
    StrategyComputed,
    TelemetryReceived,
)
from pitwall.infra.config import PitWallConfig
from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.llm import LLMClient
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector
from pitwall.ports.speech import SpeechOutput
from pitwall.ports.telemetry import TelemetrySource
from pitwall.services.nano_triage import NanoTriageService
from pitwall.services.radio import RadioService
from pitwall.services.reflex.engine import ReflexEngine
from pitwall.services.reflex.registry import RuleRegistry
from pitwall.services.reflex.rules.fuel_critical import check_fuel_critical
from pitwall.services.reflex.rules.gap_alert import check_gap_alert
from pitwall.services.reflex.rules.tire_deg import check_tire_degradation
from pitwall.services.reflex.rules.weather_change import check_weather_change
from pitwall.services.strategist import UltraStrategistService
from pitwall.services.watchdog import WatchdogService

logger = logging.getLogger(__name__)


# ── Adapter factories ────────────────────────────────────────────────────


def _build_clock() -> Clock:
    return SystemClock()


def _build_telemetry(cfg: PitWallConfig, clock: Clock) -> TelemetrySource:
    if cfg.telemetry_source == "assetto_corsa":
        return AssettoCorsaTelemetrySource(
            clock,
            session_id=cfg.session_id,
            driver_id=cfg.driver_id,
            total_laps=cfg.ac_total_laps,
            interval_sec=cfg.telemetry_interval_sec,
            fuel_per_lap_estimate_kg=cfg.ac_fuel_per_lap_estimate,
        )
    if cfg.telemetry_source == "csv_replay":
        if cfg.telemetry_csv_path is None:
            msg = "PITWALL_TELEMETRY_CSV_PATH required for csv_replay source"
            raise ValueError(msg)
        return CsvReplayTelemetrySource(
            cfg.telemetry_csv_path,
            clock,
            interval_sec=cfg.telemetry_interval_sec,
        )
    return SimulatorTelemetrySource(
        clock,
        session_id=cfg.session_id,
        driver_id=cfg.driver_id,
        total_laps=cfg.total_laps,
        interval_sec=cfg.telemetry_interval_sec,
    )


def _build_llm(cfg: PitWallConfig) -> LLMClient:
    if cfg.llm_provider == "nebius":
        return NebiusLLMClient(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_api_base_url,
            nano_model=cfg.llm_nano_model,
            ultra_model=cfg.llm_ultra_model,
            timeout_sec=cfg.llm_timeout_sec,
            max_retries=cfg.llm_max_retries,
            cb_failure_threshold=cfg.cb_failure_threshold,
            cb_recovery_timeout_sec=cfg.cb_recovery_timeout_sec,
        )
    return MockLLMClient()


def _build_speech(cfg: PitWallConfig) -> SpeechOutput:
    if cfg.speech_provider == "browser_tts":
        return BrowserTTSSpeechOutput()
    return NullSpeechOutput()


def _build_event_bus(cfg: PitWallConfig) -> AsyncEventBus:
    return AsyncEventBus(
        telemetry_queue_size=cfg.bus_telemetry_queue_size,
        critical_queue_size=cfg.bus_alert_queue_size,
    )


def _build_rule_registry() -> RuleRegistry:
    registry = RuleRegistry()
    registry.register("tire_degradation", check_tire_degradation)
    registry.register("fuel_critical", check_fuel_critical)
    registry.register("weather_change", check_weather_change)
    registry.register("gap_alert", check_gap_alert)
    return registry


# ── Pipeline runner ──────────────────────────────────────────────────────


async def _ingest_telemetry(
    source: TelemetrySource,
    bus: EventBus,
    reflex: ReflexEngine,
    clock: Clock,
    log: StructuredLogger,
) -> None:
    """Consume telemetry frames, publish events, and run reflex rules."""
    async for frame in source.stream():
        await bus.publish(
            TelemetryReceived(
                frame=frame,
                correlation_id=uuid4(),
                timestamp=clock.now(),
            )
        )
        await reflex.evaluate(frame)


async def run(config: PitWallConfig | None = None) -> None:
    """Build the object graph, wire subscriptions, and run the pipeline.

    This is the single entry point for the application.  Everything
    is constructed here via dependency injection — no globals, no
    singletons.
    """
    cfg = config or PitWallConfig()

    # ── Build adapters ───────────────────────────────────────
    clock = _build_clock()
    log = JsonStructuredLogger(level=cfg.log_level)
    metrics = InMemoryMetricsCollector()
    bus = _build_event_bus(cfg)
    llm = _build_llm(cfg)
    speech = _build_speech(cfg)
    storage = JsonFileStorage(cfg.storage_path)
    telemetry = _build_telemetry(cfg, clock)

    # ── Build services ───────────────────────────────────────
    registry = _build_rule_registry()
    reflex = ReflexEngine(registry, bus, clock, log, metrics)
    nano = NanoTriageService(llm, bus, clock, log, metrics)
    strategist = UltraStrategistService(llm, bus, clock, log, metrics)
    radio = RadioService(speech, bus, clock, log, metrics)
    watchdog = WatchdogService(
        clock, log, metrics, bus,
        telemetry_timeout_sec=cfg.telemetry_interval_sec * 5,
    )

    # ── Wire subscriptions ───────────────────────────────────
    bus.subscribe(TelemetryReceived, watchdog.on_telemetry)
    bus.subscribe(AlertRaised, nano.handle_alert)
    bus.subscribe(AlertRaised, watchdog.on_alert_raised)
    bus.subscribe(AlertTriaged, strategist.handle_triaged)
    bus.subscribe(StrategyComputed, radio.handle_strategy)
    bus.subscribe(RadioCallReady, radio.handle_radio_ready)
    bus.subscribe(RadioCallReady, watchdog.on_radio_ready)

    # ── Start ────────────────────────────────────────────────
    log.info("PitWall AI starting", provider=cfg.llm_provider, source=cfg.telemetry_source)
    await bus.start()
    await watchdog.start()

    shutdown = asyncio.Event()

    def _signal_handler() -> None:
        log.info("Shutdown signal received")
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals.
            pass

    try:
        ingest_task = asyncio.create_task(
            _ingest_telemetry(telemetry, bus, reflex, clock, log)
        )
        shutdown_task = asyncio.create_task(shutdown.wait())

        done, pending = await asyncio.wait(
            {ingest_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    finally:
        # ── Clean shutdown ───────────────────────────────────
        log.info("Shutting down…")
        await telemetry.close()
        await watchdog.stop()
        await bus.stop()

        # Persist final metrics.
        await storage.save("last_session_metrics", metrics.snapshot())

        close_fn = getattr(llm, "close", None)
        if callable(close_fn):
            await close_fn()

        log.info("PitWall AI stopped")


def main() -> None:
    """CLI entry point."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
