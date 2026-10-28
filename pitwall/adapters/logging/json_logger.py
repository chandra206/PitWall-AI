"""Adapter: structured JSON logger with correlation IDs.

Emits one JSON line per log entry to the standard Python logging system,
suitable for structured log aggregation (e.g. Datadog, CloudWatch).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pitwall.ports.logger import StructuredLogger


class JsonStructuredLogger(StructuredLogger):
    """Emit structured JSON log lines with correlation IDs.

    Wraps the standard ``logging`` library so that output can be captured
    by any Python log handler while remaining machine-parseable.
    """

    def __init__(self, name: str = "pitwall", level: str = "INFO") -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)

    def info(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        self._emit("INFO", message, correlation_id, context)

    def warning(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        self._emit("WARNING", message, correlation_id, context)

    def error(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        self._emit("ERROR", message, correlation_id, context)

    def debug(
        self,
        message: str,
        *,
        correlation_id: UUID | None = None,
        **context: Any,
    ) -> None:
        self._emit("DEBUG", message, correlation_id, context)

    def _emit(
        self,
        level: str,
        message: str,
        correlation_id: UUID | None,
        context: dict[str, Any],
    ) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        if correlation_id is not None:
            entry["correlation_id"] = str(correlation_id)
        if context:
            entry["context"] = {
                k: str(v) if isinstance(v, UUID) else v
                for k, v in context.items()
            }

        log_method = getattr(self._logger, level.lower(), self._logger.info)
        log_method(json.dumps(entry, default=str))
