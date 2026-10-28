"""Correlation-ID management for tracing alerts through the pipeline.

A correlation ID is assigned when an alert enters the reflex layer and follows
the alert through Nano triage → Ultra strategist → radio, enabling structured
logging and end-to-end tracing without coupling stages directly.
"""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID, uuid4

_correlation_id_var: ContextVar[UUID | None] = ContextVar(
    "pitwall_correlation_id", default=None
)


def get_correlation_id() -> UUID:
    """Return the current correlation ID, creating one if absent."""
    cid = _correlation_id_var.get()
    if cid is None:
        cid = uuid4()
        _correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: UUID) -> None:
    """Explicitly set the correlation ID for the current context."""
    _correlation_id_var.set(cid)


def new_correlation_id() -> UUID:
    """Generate and set a fresh correlation ID, returning it."""
    cid = uuid4()
    _correlation_id_var.set(cid)
    return cid
