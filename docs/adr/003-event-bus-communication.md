# ADR-003: Event-Bus Communication Between Pipeline Stages

**Status:** Accepted
**Date:** 2025-06-15
**Deciders:** PitWall AI Team

## Context

The pipeline has four stages (reflex → Nano triage → Ultra strategist →
radio).  They must be decoupled so that:
1. Any stage can be replaced independently.
2. A stage could later move to its own process or machine.
3. Back-pressure is explicit, not accidental.

## Decision

Stages communicate exclusively through **typed domain events** published
on an **in-process async event bus** (`pitwall/adapters/bus/async_bus.py`).

Key design points:
- Events are **immutable Pydantic models** in `pitwall/domain/events.py`.
- Two internal queues enforce distinct policies:
  - **Telemetry queue**: bounded, drop-oldest when full (high-frequency, lossy).
  - **Critical queue**: bounded, blocking publisher (alerts must never be silently dropped).
- Subscribers are dispatched concurrently via `asyncio.gather`.
- No stage ever calls another stage directly or imports its module.

The event bus implements the `EventBus` port, so it can later be replaced
with an external broker (Redis Streams, Kafka, NATS) by writing a new
adapter.

## Consequences

**Positive:**
- Full decoupling — stages don't know about each other.
- Back-pressure is explicit and policy-driven.
- Migration to a distributed architecture requires only a new adapter.

**Negative:**
- Debugging async event flow is harder than synchronous call chains.
- In-process, events share memory — no serialisation overhead now, but
  a future distributed adapter would add it.
