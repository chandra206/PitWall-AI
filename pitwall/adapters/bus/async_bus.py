"""Adapter: Async event bus with bounded queues and backpressure.

Telemetry events use a drop-oldest policy when the queue is full.
Alert events use a never-drop queue that blocks the publisher.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from pitwall.domain.events import (
    AlertRaised,
    AlertTriaged,
    DomainEvent,
    RadioCallReady,
    StrategyComputed,
    TelemetryReceived,
)
from pitwall.ports.event_bus import E, EventBus, EventHandler

logger = logging.getLogger(__name__)

# Event types routed to the critical (never-drop) queue.
_CRITICAL_EVENT_TYPES: frozenset[type[DomainEvent]] = frozenset(
    {AlertRaised, AlertTriaged, StrategyComputed, RadioCallReady}
)


class AsyncEventBus(EventBus):
    """In-process async event bus backed by ``asyncio.Queue``.

    Two internal queues enforce distinct backpressure policies:
    - **Telemetry queue** (bounded, drop-oldest): high-frequency, lossy.
    - **Critical queue** (bounded, blocking): alerts must never be dropped.

    Subscribers are dispatched concurrently per event via ``asyncio.gather``.
    """

    def __init__(
        self,
        telemetry_queue_size: int = 100,
        critical_queue_size: int = 1000,
    ) -> None:
        self._subscribers: dict[
            type[DomainEvent], list[Callable[[Any], Awaitable[None]]]
        ] = defaultdict(list)
        self._telemetry_q: asyncio.Queue[DomainEvent] = asyncio.Queue(
            maxsize=telemetry_queue_size
        )
        self._critical_q: asyncio.Queue[DomainEvent] = asyncio.Queue(
            maxsize=critical_queue_size
        )
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []

    async def publish(self, event: DomainEvent) -> None:
        """Route event to the appropriate queue.

        Telemetry events use drop-oldest when full; critical events block.
        """
        if type(event) in _CRITICAL_EVENT_TYPES:
            await self._critical_q.put(event)
        else:
            # Drop-oldest for telemetry: if full, remove one and add.
            if self._telemetry_q.full():
                try:
                    self._telemetry_q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await self._telemetry_q.put(event)

    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Register *handler* for *event_type*."""
        self._subscribers[event_type].append(handler)

    async def start(self) -> None:
        """Start the consumer tasks for both queues."""
        self._running = True
        self._tasks.append(
            asyncio.create_task(self._consume(self._telemetry_q, "telemetry"))
        )
        self._tasks.append(
            asyncio.create_task(self._consume(self._critical_q, "critical"))
        )
        logger.info("AsyncEventBus started")

    async def stop(self) -> None:
        """Signal stop, drain remaining events, cancel consumer tasks."""
        self._running = False
        # Drain remaining events before cancelling.
        for q in (self._critical_q, self._telemetry_q):
            while not q.empty():
                try:
                    event = q.get_nowait()
                    await self._dispatch(event)
                except asyncio.QueueEmpty:
                    break

        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("AsyncEventBus stopped")

    async def _consume(self, queue: asyncio.Queue[DomainEvent], name: str) -> None:
        """Loop: pull events from *queue* and dispatch to subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                await self._dispatch(event)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def _dispatch(self, event: DomainEvent) -> None:
        """Call all subscribers registered for this event type."""
        handlers = self._subscribers.get(type(event), [])
        if not handlers:
            return
        results = await asyncio.gather(
            *(h(event) for h in handlers),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(
                    "Handler %s failed for %s: %s",
                    handlers[i].__qualname__,
                    type(event).__name__,
                    result,
                )
