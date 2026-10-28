"""Reflex rule: gap alert.

Pure function — warns when the car behind is within DRS/undercut range.
"""

from __future__ import annotations

from pitwall.domain.enums import AlertSeverity
from pitwall.domain.models import AlertSpec, TelemetryFrame

CRITICAL_GAP_SEC = 0.5
WARNING_GAP_SEC = 1.0


def check_gap_alert(frame: TelemetryFrame) -> AlertSpec | None:
    """Detect dangerously small gap to the car behind (undercut risk)."""
    if frame.gap_behind_sec is None:
        return None

    if frame.gap_behind_sec <= CRITICAL_GAP_SEC:
        return AlertSpec(
            severity=AlertSeverity.CRITICAL,
            rule_name="gap_alert",
            message=(
                f"Car behind within {frame.gap_behind_sec:.1f}s — "
                f"undercut imminent, lap {frame.lap}"
            ),
        )
    if frame.gap_behind_sec <= WARNING_GAP_SEC:
        return AlertSpec(
            severity=AlertSeverity.WARNING,
            rule_name="gap_alert",
            message=(
                f"Car behind within {frame.gap_behind_sec:.1f}s — "
                f"undercut risk, lap {frame.lap}"
            ),
        )
    return None
