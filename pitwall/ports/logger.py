"""Port: StructuredLogger — JSON logging with correlation IDs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class StructuredLogger(ABC):
    """Abstract structured logger that emits JSON with correlation IDs.

    Every log entry can carry a ``correlation_id`` that traces one alert
    from reflex → Nano → Ultra → radio, enabling end-to-end debugging.
    """

    @abstractmethod
    def info(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        """Log an informational message."""
        ...

    @abstractmethod
    def warning(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        """Log a warning."""
        ...

    @abstractmethod
    def error(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        """Log an error."""
        ...

    @abstractmethod
    def debug(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        """Log a debug message."""
        ...
