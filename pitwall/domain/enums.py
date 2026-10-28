"""Domain enumerations used across the pit-wall pipeline."""

from __future__ import annotations

from enum import Enum


class AlertSeverity(str, Enum):
    """How urgent an alert is — drives queue routing and radio priority."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TireCompound(str, Enum):
    """Available tire compounds in a race weekend."""

    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    INTERMEDIATE = "intermediate"
    WET = "wet"


class StrategyAction(str, Enum):
    """Atomic actions the strategist can recommend."""

    PIT_NOW = "pit_now"
    PIT_NEXT_LAP = "pit_next_lap"
    EXTEND_STINT = "extend_stint"
    PUSH = "push"
    SAVE_TIRES = "save_tires"
    BOX_BOX = "box_box"
    STAY_OUT = "stay_out"
    DEFEND = "defend"
    ATTACK = "attack"


class PipelineStage(str, Enum):
    """Stages in the real-time processing pipeline."""

    REFLEX = "reflex"
    NANO_TRIAGE = "nano_triage"
    ULTRA_STRATEGIST = "ultra_strategist"
    RADIO = "radio"


class WeatherCondition(str, Enum):
    """Current or forecast weather state."""

    DRY = "dry"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    MIXED = "mixed"


class CircuitState(str, Enum):
    """State of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
