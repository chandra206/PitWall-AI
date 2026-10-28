"""Port: TelemetrySource — async stream of car telemetry frames."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from pitwall.domain.models import TelemetryFrame


class TelemetrySource(ABC):
    """Abstract source of real-time telemetry data.

    Implementations may connect to a live simulator, replay a CSV file,
    or generate synthetic data.  The caller iterates with ``async for``.
    """

    @abstractmethod
    def stream(self) -> AsyncIterator[TelemetryFrame]:
        """Yield telemetry frames as they arrive.

        The iterator should respect cancellation and clean up resources
        when the caller breaks out of the loop.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by this source."""
        ...
