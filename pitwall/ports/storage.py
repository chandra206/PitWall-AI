"""Port: Storage — persistent key-value store for session data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Storage(ABC):
    """Abstract key-value storage for persisting session state.

    Implementations may write to JSON files, a database, or an
    in-memory dict (for tests).
    """

    @abstractmethod
    async def save(self, key: str, data: dict[str, Any]) -> None:
        """Persist ``data`` under ``key``, overwriting any existing value."""
        ...

    @abstractmethod
    async def load(self, key: str) -> dict[str, Any] | None:
        """Load data by ``key``, returning ``None`` if not found."""
        ...
