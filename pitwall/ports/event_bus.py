"""Port: EventBus — typed publish/subscribe for pipeline stages.

Stages communicate *only* through the event bus, never by direct calls.
This enables replacing or moving any stage to its own process later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pitwall.domain.events import DomainEvent

E = TypeVar("E", bound=DomainEvent)

# Handler receives the event and returns nothing (may be async).
EventHandler = Callable[[E], Awaitable[None]]


class EventBus(ABC):
    """Abstract in-process event bus with bounded queues.

    Implementations must enforce:
    - Bounded queue sizes with an explicit backpressure policy.
    - Drop-oldest for telemetry events, never-drop for critical alerts.
    - Clean shutdown that drains in-flight events.
    """

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered subscribers.

        If the target queue is full, the backpressure policy determines
        whether old events are evicted or the call blocks.
        """
        ...

    @abstractmethod
    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Register an async handler for a specific event type.

        Multiple handlers may be registered for the same event type.
        Handlers are called concurrently for a given event.
        """
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start consuming events from internal queues."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop consuming and drain remaining events gracefully."""
        ...
