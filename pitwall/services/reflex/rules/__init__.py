"""Built-in reflex rules — each is a pure function registered on import."""

from pitwall.services.reflex.rules.fuel_critical import check_fuel_critical
from pitwall.services.reflex.rules.gap_alert import check_gap_alert
from pitwall.services.reflex.rules.tire_deg import check_tire_degradation
from pitwall.services.reflex.rules.weather_change import check_weather_change

__all__ = [
    "check_fuel_critical",
    "check_gap_alert",
    "check_tire_degradation",
    "check_weather_change",
]
