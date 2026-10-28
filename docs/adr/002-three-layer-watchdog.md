# ADR-002: Three-Layer Watchdog

**Status:** Accepted
**Date:** 2025-06-15
**Deciders:** PitWall AI Team

## Context

A real-time system that advises race strategy must detect when it is no
longer functioning correctly — stale data, stuck pipeline stages, or
silent failures in downstream services.  A single health-check is too
coarse; we need granular visibility.

## Decision

Implement a **three-layer watchdog service** (`pitwall/services/watchdog.py`):

| Layer | What it monitors | Alert condition |
|-------|-----------------|-----------------|
| 1 — Telemetry liveness | Time since last `TelemetryReceived` | Exceeds `telemetry_timeout_sec` |
| 2 — Pipeline throughput | Time from `AlertRaised` to `RadioCallReady` | Exceeds `pipeline_timeout_sec` |
| 3 — Periodic health | Metrics snapshot every N seconds | Emits for dashboard / alerting |

The watchdog subscribes to the same event bus as every other stage, using
`correlation_id` to match entry and exit events for latency measurement.

## Consequences

**Positive:**
- Operators see telemetry staleness, pipeline latency, and overall health
  in one metrics snapshot.
- Degradation is detected automatically — not just when the driver
  notices silence.

**Negative:**
- Three background loops add minor CPU overhead.
- Thresholds must be tuned per deployment (simulator vs. live).
