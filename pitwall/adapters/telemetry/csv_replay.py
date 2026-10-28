"""Adapter: CSV replay telemetry source.

Replays historical telemetry from a CSV file, emitting one frame per row
at a configurable interval.
"""

from __future__ import annotations

import asyncio
import csv
from collections.abc import AsyncIterator
from pathlib import Path

from pitwall.domain.enums import TireCompound, WeatherCondition
from pitwall.domain.models import TelemetryFrame
from pitwall.ports.clock import Clock
from pitwall.ports.telemetry import TelemetrySource


class CsvReplayTelemetrySource(TelemetrySource):
    """Replay telemetry from a CSV file.

    The CSV must have headers matching ``TelemetryFrame`` field names.
    Missing optional fields are filled with defaults.
    """

    def __init__(
        self,
        csv_path: str | Path,
        clock: Clock,
        *,
        interval_sec: float = 1.0,
    ) -> None:
        self._path = Path(csv_path)
        self._clock = clock
        self._interval = interval_sec
        self._closed = False

        if not self._path.exists():
            msg = f"CSV file not found: {self._path}"
            raise FileNotFoundError(msg)

    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        """Yield one ``TelemetryFrame`` per CSV row."""
        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                if self._closed:
                    break

                frame = TelemetryFrame(
                    session_id=row.get("session_id", "csv_session"),
                    driver_id=row.get("driver_id", "driver_01"),
                    lap=int(row["lap"]),
                    position=int(row.get("position", "1")),
                    tire_compound=TireCompound(row.get("tire_compound", "medium")),
                    tire_age=int(row.get("tire_age", "0")),
                    tire_wear_pct=float(row.get("tire_wear_pct", "0")),
                    fuel_remaining_kg=float(row.get("fuel_remaining_kg", "100")),
                    fuel_per_lap_kg=float(row.get("fuel_per_lap_kg", "1.8")),
                    gap_ahead_sec=float(row["gap_ahead_sec"]) if row.get("gap_ahead_sec") else None,
                    gap_behind_sec=float(row["gap_behind_sec"]) if row.get("gap_behind_sec") else None,
                    last_lap_time_sec=float(row["last_lap_time_sec"]) if row.get("last_lap_time_sec") else None,
                    speed_kph=float(row.get("speed_kph", "0")),
                    weather=WeatherCondition(row.get("weather", "dry")),
                    track_temp_c=float(row.get("track_temp_c", "30")),
                    air_temp_c=float(row.get("air_temp_c", "25")),
                    rain_chance_pct=float(row.get("rain_chance_pct", "0")),
                    total_laps=int(row.get("total_laps", "57")),
                    timestamp=self._clock.now(),
                )
                yield frame
                await asyncio.sleep(self._interval)

    async def close(self) -> None:
        """Signal the stream to stop."""
        self._closed = True
