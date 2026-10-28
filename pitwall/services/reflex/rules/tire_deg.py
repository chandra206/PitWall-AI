"""Reflex rule: tire degradation.

Pure function — no I/O, no side effects.  Returns ``AlertSpec`` when
tire wear exceeds warning (≥ 70 %) or critical (≥ 90 %) thresholds.
"""

from __future__ import annotations

from pitwall.domain.enums import AlertSeverity
from pitwall.domain.models import AlertSpec, TelemetryFrame

CRITICAL_WEAR_PCT = 90.0
WARNING_WEAR_PCT = 70.0


def check_tire_degradation(frame: TelemetryFrame) -> AlertSpec | None:
    """Detect dangerously high tire wear."""
    if frame.tire_wear_pct >= CRITICAL_WEAR_PCT:
        return AlertSpec(
            severity=AlertSeverity.CRITICAL,
            rule_name="tire_degradation",
            message=(
                f"Critical tire wear at {frame.tire_wear_pct:.1f}% "
                f"on {frame.tire_compound.value}s, lap {frame.lap}"
            ),
        )
    if frame.tire_wear_pct >= WARNING_WEAR_PCT:
        return AlertSpec(
            severity=AlertSeverity.WARNING,
            rule_name="tire_degradation",
            message=(
                f"High tire wear at {frame.tire_wear_pct:.1f}% "
                f"on {frame.tire_compound.value}s, lap {frame.lap}"
            ),
        )
    return None
