"""Adapter: JSON file storage for session persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pitwall.ports.storage import Storage


class JsonFileStorage(Storage):
    """Persist data as JSON files in a configurable directory.

    Each key maps to ``{storage_dir}/{key}.json``.
    """

    def __init__(self, storage_dir: str | Path) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    async def save(self, key: str, data: dict[str, Any]) -> None:
        """Write ``data`` to ``{key}.json``."""
        path = self._dir / f"{key}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    async def load(self, key: str) -> dict[str, Any] | None:
        """Read ``{key}.json``, returning ``None`` if it doesn't exist."""
        path = self._dir / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
