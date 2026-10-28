# ADR-001: Ports-and-Adapters (Hexagonal) Architecture

**Status:** Accepted
**Date:** 2025-06-15
**Deciders:** PitWall AI Team

## Context

PitWall AI must integrate with multiple external systems (telemetry feeds,
LLM APIs, TTS engines, storage backends) that change independently.  We
need to swap providers — e.g. replacing Nebius with OpenAI, or CSV replay
with a live simulator — without modifying business logic.

## Decision

Adopt **hexagonal architecture** (ports-and-adapters):

- **Ports** are abstract interfaces (`TelemetrySource`, `LLMClient`,
  `SpeechOutput`, `EventBus`, `Clock`, `Storage`, `StructuredLogger`,
  `MetricsCollector`) defined in `pitwall/ports/`.
- **Adapters** are concrete implementations in `pitwall/adapters/` that
  fulfil one port each.
- **Services** in `pitwall/services/` contain business logic and depend
  only on domain models and port interfaces.
- **Composition root** (`pitwall/app/main.py`) is the only module that
  knows concrete adapter classes and wires them via constructor injection.

Dependency direction is enforced by **import-linter** in CI:
`domain → nothing; ports → domain; services → domain+ports; adapters → domain+ports+infra; app → everything`.

## Consequences

**Positive:**
- Swapping a model, TTS, or data source is a config change + one new adapter.
- Services are testable with fake adapters — no network, no real time.
- Architecture constraints are machine-checked; violations fail the build.

**Negative:**
- More files and indirection than a flat script.
- New contributors must understand the port/adapter pattern.

## Tradeoff

The indirection cost is justified because the system is designed for rapid
iteration on AI providers and telemetry sources.  The import-linter guard
prevents the architecture from degrading over time.
