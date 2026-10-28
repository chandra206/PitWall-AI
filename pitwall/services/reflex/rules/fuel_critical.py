"""Reflex rule: fuel critical.

Pure function — compares remaining fuel against the fuel needed to
finish the race at the current consumption rate.
"""

from __future__ import annotations

from pitwall.domain.enums import AlertSeverity
from pitwall.domain.models import AlertSpec, TelemetryFrame


def check_fuel_critical(frame: TelemetryFrame) -> AlertSpec | None:
    """Detect when fuel is insufficient to finish the race."""
    if frame.fuel_per_lap_kg <= 0:
        return None

    laps_remaining = frame.total_laps - frame.lap
    if laps_remaining <= 0:
        return None

    fuel_needed = laps_remaining * frame.fuel_per_lap_kg
    fuel_deficit = fuel_needed - frame.fuel_remaining_kg

    if fuel_deficit > frame.fuel_per_lap_kg * 2:
        return AlertSpec(
            severity=AlertSeverity.CRITICAL,
            rule_name="fuel_critical",
            message=(
                f"Fuel critical: {frame.fuel_remaining_kg:.1f} kg remaining, "
                f"need {fuel_needed:.1f} kg for {laps_remaining} laps"
            ),
        )
    if fuel_deficit > 0:
        return AlertSpec(
            severity=AlertSeverity.WARNING,
            rule_name="fuel_critical",
            message=(
                f"Fuel marginal: {frame.fuel_remaining_kg:.1f} kg remaining, "
                f"need {fuel_needed:.1f} kg for {laps_remaining} laps"
            ),
        )
    return None
