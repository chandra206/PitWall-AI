"""Reflex rule: weather change.

Pure function — warns when rain probability is high while the car
is on dry-compound tires.
"""

from __future__ import annotations

from pitwall.domain.enums import AlertSeverity, TireCompound
from pitwall.domain.models import AlertSpec, TelemetryFrame

_DRY_COMPOUNDS = frozenset({TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD})

CRITICAL_RAIN_PCT = 80.0
WARNING_RAIN_PCT = 50.0


def check_weather_change(frame: TelemetryFrame) -> AlertSpec | None:
    """Detect high rain probability with dry tires fitted."""
    on_drys = frame.tire_compound in _DRY_COMPOUNDS

    if not on_drys:
        return None

    if frame.rain_chance_pct >= CRITICAL_RAIN_PCT:
        return AlertSpec(
            severity=AlertSeverity.CRITICAL,
            rule_name="weather_change",
            message=(
                f"Rain probability {frame.rain_chance_pct:.0f}% "
                f"with {frame.tire_compound.value} tires — pit for inters/wets"
            ),
        )
    if frame.rain_chance_pct >= WARNING_RAIN_PCT:
        return AlertSpec(
            severity=AlertSeverity.WARNING,
            rule_name="weather_change",
            message=(
                f"Rain probability rising: {frame.rain_chance_pct:.0f}% "
                f"with {frame.tire_compound.value} tires"
            ),
        )
    return None
