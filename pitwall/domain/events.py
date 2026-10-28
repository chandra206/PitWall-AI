"""Typed domain events that flow through the async event bus.

Each event is immutable and carries a ``correlation_id`` that traces the
alert from reflex → Nano → Ultra → radio for structured logging.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from pitwall.domain.models import (
    Alert,
    RadioCall,
    StrategyRecommendation,
    TelemetryFrame,
    TriageResult,
)


class DomainEvent(BaseModel):
    """Base class for all domain events on the event bus."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime


class TelemetryReceived(DomainEvent):
    """A new telemetry frame has arrived from the data source."""

    frame: TelemetryFrame


class AlertRaised(DomainEvent):
    """The reflex layer detected a condition that needs attention."""

    alert: Alert


class AlertTriaged(DomainEvent):
    """The Nano model has scored and classified an alert."""

    triage: TriageResult
    original_alert: Alert


class StrategyComputed(DomainEvent):
    """The Ultra model has produced a strategy recommendation."""

    strategy: StrategyRecommendation
    original_alert: Alert


class RadioCallReady(DomainEvent):
    """A radio message is composed and ready for TTS output."""

    radio_call: RadioCall
