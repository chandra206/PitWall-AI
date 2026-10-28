"""Adapter: simulated telemetry source for development and demos.

Generates realistic-looking telemetry frames with gradual tire wear,
fuel consumption, and occasional weather/gap changes.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator

from pitwall.domain.enums import TireCompound, WeatherCondition
from pitwall.domain.models import TelemetryFrame
from pitwall.ports.clock import Clock
from pitwall.ports.telemetry import TelemetrySource


class SimulatorTelemetrySource(TelemetrySource):
    """Generate synthetic telemetry frames at a configurable interval.

    Simulates a race with monotonically increasing tire wear, decreasing
    fuel, and stochastic gaps and weather changes.
    """

    def __init__(
        self,
        clock: Clock,
        *,
        session_id: str = "sim_session",
        driver_id: str = "driver_01",
        total_laps: int = 57,
        interval_sec: float = 1.0,
    ) -> None:
        self._clock = clock
        self._session_id = session_id
        self._driver_id = driver_id
        self._total_laps = total_laps
        self._interval = interval_sec
        self._closed = False

    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        """Yield one frame per simulated lap at ``interval_sec`` rate."""
        tire_wear = 0.0
        fuel = 110.0  # kg at race start
        fuel_per_lap = 1.8
        compound = TireCompound.MEDIUM
        tire_age = 0

        for lap in range(1, self._total_laps + 1):
            if self._closed:
                break

            # Simulate gradual changes.
            tire_wear = min(100.0, tire_wear + random.uniform(1.2, 2.8))
            fuel = max(0.0, fuel - fuel_per_lap + random.uniform(-0.1, 0.1))
            tire_age += 1
            rain_chance = min(100.0, max(0.0, random.gauss(20, 25)))

            gap_behind: float | None = round(random.uniform(0.3, 5.0), 1)
            gap_ahead: float | None = round(random.uniform(0.5, 6.0), 1)

            weather = WeatherCondition.DRY
            if rain_chance > 60:
                weather = WeatherCondition.LIGHT_RAIN
            if rain_chance > 85:
                weather = WeatherCondition.HEAVY_RAIN

            frame = TelemetryFrame(
                session_id=self._session_id,
                driver_id=self._driver_id,
                lap=lap,
                position=random.randint(1, 20),
                tire_compound=compound,
                tire_age=tire_age,
                tire_wear_pct=round(tire_wear, 1),
                fuel_remaining_kg=round(fuel, 1),
                fuel_per_lap_kg=fuel_per_lap,
                gap_ahead_sec=gap_ahead,
                gap_behind_sec=gap_behind,
                last_lap_time_sec=round(random.uniform(78.0, 82.0), 3),
                speed_kph=round(random.uniform(280, 330), 1),
                weather=weather,
                track_temp_c=round(random.uniform(28, 45), 1),
                air_temp_c=round(random.uniform(22, 35), 1),
                rain_chance_pct=round(rain_chance, 1),
                total_laps=self._total_laps,
                timestamp=self._clock.now(),
            )
            yield frame
            await asyncio.sleep(self._interval)

    async def close(self) -> None:
        """Signal the stream to stop."""
        self._closed = True
