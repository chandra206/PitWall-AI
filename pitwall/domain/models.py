"""Pydantic domain models — the versioned data contracts for every boundary.

Every model is frozen (immutable) to prevent accidental mutation as events
flow through the pipeline.  Timestamps are **not** auto-generated so that
the service layer can inject a ``Clock`` for full testability.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from pitwall.domain.enums import (
    AlertSeverity,
    PipelineStage,
    StrategyAction,
    TireCompound,
    WeatherCondition,
)


# ── Telemetry ────────────────────────────────────────────────────────────────


class TelemetryFrame(BaseModel):
    """A single, immutable snapshot of car telemetry at a point in time."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    driver_id: str
    lap: int = Field(ge=0)
    position: int = Field(ge=1)
    tire_compound: TireCompound
    tire_age: int = Field(ge=0, description="Laps on the current set of tires")
    tire_wear_pct: float = Field(ge=0.0, le=100.0)
    fuel_remaining_kg: float = Field(ge=0.0)
    fuel_per_lap_kg: float = Field(ge=0.0)
    gap_ahead_sec: float | None = None
    gap_behind_sec: float | None = None
    last_lap_time_sec: float | None = None
    sector_times_sec: tuple[float, ...] = Field(default_factory=tuple)
    speed_kph: float = Field(ge=0.0, default=0.0)
    weather: WeatherCondition = WeatherCondition.DRY
    track_temp_c: float = 30.0
    air_temp_c: float = 25.0
    rain_chance_pct: float = Field(ge=0.0, le=100.0, default=0.0)
    total_laps: int = Field(ge=1, default=57)
    timestamp: datetime


# ── Reflex output ────────────────────────────────────────────────────────────


class AlertSpec(BaseModel):
    """Lightweight descriptor returned by a pure reflex rule.

    Contains only the *detection logic* output — no IDs, no timestamps.
    The ``ReflexEngine`` enriches this into a full ``Alert``.
    """

    model_config = ConfigDict(frozen=True)

    severity: AlertSeverity
    rule_name: str
    message: str


# ── Pipeline models ──────────────────────────────────────────────────────────


class Alert(BaseModel):
    """An alert raised by the reflex layer, enriched with IDs and timing."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    severity: AlertSeverity
    source_stage: PipelineStage
    rule_name: str
    message: str
    telemetry_snapshot: TelemetryFrame
    timestamp: datetime


class TriageResult(BaseModel):
    """Result of Nano-model triage — should this alert reach the strategist?"""

    model_config = ConfigDict(frozen=True)

    alert_id: UUID
    correlation_id: UUID
    priority_score: float = Field(ge=0.0, le=1.0)
    needs_strategy: bool
    summary: str
    reasoning: str
    timestamp: datetime


class StrategyRecommendation(BaseModel):
    """Strategy produced by the Ultra-model strategist."""

    model_config = ConfigDict(frozen=True)

    correlation_id: UUID
    actions: tuple[StrategyAction, ...] = Field(min_length=1)
    primary_action: StrategyAction
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    pit_window_start: int | None = None
    pit_window_end: int | None = None
    recommended_compound: TireCompound | None = None
    timestamp: datetime


class RadioCall(BaseModel):
    """A composed radio message ready for TTS output."""

    model_config = ConfigDict(frozen=True)

    correlation_id: UUID
    message: str
    priority: AlertSeverity
    source_stage: PipelineStage
    timestamp: datetime
