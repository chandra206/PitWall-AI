"""Adapter: Assetto Corsa shared-memory telemetry source.

Reads live telemetry from Assetto Corsa via Windows memory-mapped files
(``acpmf_physics``, ``acpmf_graphics``, ``acpmf_static``).  These are
created by the game engine while a session is active.

This adapter maps AC's native ctypes structs onto PitWall AI's
``TelemetryFrame`` domain model.  The stream polls at a configurable
interval (default 1 Hz — fast enough for pit-wall strategy, low enough
to avoid flooding the pipeline).
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import mmap
from collections.abc import AsyncIterator
from ctypes import c_float, c_int32, c_wchar

from pitwall.domain.enums import TireCompound, WeatherCondition
from pitwall.domain.models import TelemetryFrame
from pitwall.ports.clock import Clock
from pitwall.ports.telemetry import TelemetrySource

logger = logging.getLogger(__name__)


# ── Assetto Corsa shared-memory structs ──────────────────────────────────


class SPageFilePhysics(ctypes.Structure):
    """Mirror of AC's Physics shared-memory page (``acpmf_physics``)."""

    _pack_ = 4
    _fields_ = [
        ("packetId", c_int32),
        ("gas", c_float),
        ("brake", c_float),
        ("fuel", c_float),
        ("gear", c_int32),
        ("rpms", c_int32),
        ("steerAngle", c_float),
        ("speedKmh", c_float),
        ("velocity", c_float * 3),
        ("accG", c_float * 3),
        ("wheelSlip", c_float * 4),
        ("wheelLoad", c_float * 4),
        ("wheelsPressure", c_float * 4),
        ("wheelAngularSpeed", c_float * 4),
        ("tyreWear", c_float * 4),
        ("tyreDirtyLevel", c_float * 4),
        ("tyreCoreTemperature", c_float * 4),
        ("camberRAD", c_float * 4),
        ("suspensionTravel", c_float * 4),
        ("drs", c_float),
        ("tc", c_float),
        ("heading", c_float),
        ("pitch", c_float),
        ("roll", c_float),
        ("cgHeight", c_float),
        ("carDamage", c_float * 5),
        ("numberOfTyresOut", c_int32),
        ("pitLimiterOn", c_int32),
        ("abs", c_float),
        ("kersCharge", c_float),
        ("kersInput", c_float),
        ("autoShifterOn", c_int32),
        ("rideHeight", c_float * 2),
        ("turboBoost", c_float),
        ("ballast", c_float),
        ("airDensity", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("localVelocity", c_float * 3),
        ("finalFF", c_float),
        ("performanceMeter", c_float),
        ("engineBrake", c_int32),
        ("ersRecoveryLevel", c_int32),
        ("ersPowerLevel", c_int32),
        ("ersHeatCharging", c_int32),
        ("ersIsCharging", c_int32),
        ("kersCurrentKJ", c_float),
        ("drsAvailable", c_int32),
        ("drsEnabled", c_int32),
        ("brakeBias", c_float),
        # Remaining fields that vary by AC version — not needed for PitWall.
    ]


class SPageFileGraphic(ctypes.Structure):
    """Mirror of AC's Graphics shared-memory page (``acpmf_graphics``)."""

    _pack_ = 4
    _fields_ = [
        ("packetId", c_int32),
        ("status", c_int32),
        ("session", c_int32),
        ("currentTime", c_wchar * 15),
        ("lastTime", c_wchar * 15),
        ("bestTime", c_wchar * 15),
        ("split", c_wchar * 15),
        ("completedLaps", c_int32),
        ("position", c_int32),
        ("iCurrentTime", c_int32),
        ("iLastTime", c_int32),
        ("iBestTime", c_int32),
        ("sessionTimeLeft", c_float),
        ("distanceTraveled", c_float),
        ("isPit", c_int32),
        ("carCenterCoordinates", c_float * 3),
        ("numberOfTyresOut", c_int32),
        ("lastSectorTime", c_int32),
        ("carInPitline", c_int32),
        ("carInPit", c_int32),
    ]


class SPageFileStatic(ctypes.Structure):
    """Mirror of AC's Static shared-memory page (``acpmf_static``)."""

    _pack_ = 4
    _fields_ = [
        ("smVersion", c_wchar * 15),
        ("acVersion", c_wchar * 15),
        ("numberOfSessions", c_int32),
        ("numCars", c_int32),
        ("carModel", c_wchar * 33),
        ("track", c_wchar * 33),
        ("playerName", c_wchar * 33),
        ("playerSurname", c_wchar * 33),
        ("playerNick", c_wchar * 33),
        ("sectorCount", c_int32),
        ("maxTorque", c_float),
        ("maxPower", c_float),
        ("maxRpm", c_int32),
        ("maxFuel", c_float),
        ("suspensionMaxTravel", c_float * 4),
        ("tireRadius", c_float * 4),
        ("maxTurboBoost", c_float),
        ("deprecated1", c_float),
        ("deprecated2", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("localFlg", c_int32),
        ("globalFlg", c_int32),
        ("pitWindowStart", c_int32),
        ("pitWindowEnd", c_int32),
        ("isOnline", c_int32),
    ]


# ── Helpers ──────────────────────────────────────────────────────────────


def _avg_tyre_wear_pct(wear_array: ctypes.Array[c_float]) -> float:
    """Convert AC's per-wheel wear (0.0 = new → ~1.0 = worn) to a 0-100% average."""
    values = [float(wear_array[i]) for i in range(4)]
    avg = sum(values) / 4.0
    # AC reports wear as 0.0 (fresh) to ~1.0+ (fully worn).
    return round(min(max(avg * 100.0, 0.0), 100.0), 1)


def _map_tire_compound(compound_str: str) -> TireCompound:
    """Best-effort mapping from AC's tyre compound name to domain enum."""
    lower = compound_str.strip().lower()
    if "soft" in lower:
        return TireCompound.SOFT
    if "hard" in lower:
        return TireCompound.HARD
    if "inter" in lower:
        return TireCompound.INTERMEDIATE
    if "wet" in lower:
        return TireCompound.WET
    # Default to MEDIUM for street/medium/unknown compounds.
    return TireCompound.MEDIUM


def _map_weather(road_temp: float, road_wetness: float | None = None) -> WeatherCondition:
    """Heuristic weather mapping from road conditions.

    AC (vanilla) doesn't expose rain natively — mods like Sol/CSP add it.
    We use road temperature as a coarse proxy and return DRY by default.
    """
    # If a wetness value is available (CSP extended physics), use it.
    if road_wetness is not None and road_wetness > 0.5:
        return WeatherCondition.HEAVY_RAIN if road_wetness > 0.8 else WeatherCondition.LIGHT_RAIN
    return WeatherCondition.DRY


def _parse_last_lap_ms(ms_value: int) -> float | None:
    """Convert AC's last-lap time in milliseconds to seconds, or None if invalid."""
    if ms_value <= 0:
        return None
    return round(ms_value / 1000.0, 3)


# ── Adapter ──────────────────────────────────────────────────────────────


class ACSharedMemoryError(Exception):
    """Raised when Assetto Corsa shared memory cannot be accessed."""


class AssettoCorsaTelemetrySource(TelemetrySource):
    """Read live telemetry from Assetto Corsa via Windows shared memory.

    The game must be running with an active session for the memory-mapped
    files to exist.  If the game isn't running, ``stream()`` will wait
    and retry until the connection is established or the source is closed.
    """

    # AC session status values (from Graphics.status).
    _STATUS_OFF = 0
    _STATUS_REPLAY = 1
    _STATUS_LIVE = 2
    _STATUS_PAUSE = 3

    def __init__(
        self,
        clock: Clock,
        *,
        session_id: str = "ac_live",
        driver_id: str = "player",
        total_laps: int = 0,
        interval_sec: float = 1.0,
        fuel_per_lap_estimate_kg: float = 2.5,
    ) -> None:
        self._clock = clock
        self._session_id = session_id
        self._driver_id = driver_id
        self._total_laps = total_laps
        self._interval = interval_sec
        self._fuel_per_lap_est = fuel_per_lap_estimate_kg
        self._closed = False

        self._phys_mmap: mmap.mmap | None = None
        self._gfx_mmap: mmap.mmap | None = None
        self._static_mmap: mmap.mmap | None = None

        self._physics: SPageFilePhysics | None = None
        self._graphics: SPageFileGraphic | None = None
        self._static: SPageFileStatic | None = None

        self._prev_fuel: float | None = None
        self._prev_lap: int = -1
        self._fuel_per_lap_samples: list[float] = []

    # ── Connection management ────────────────────────────────────────

    def _connect(self) -> bool:
        """Attempt to open AC shared memory.  Returns True on success."""
        try:
            self._phys_mmap = mmap.mmap(
                0, ctypes.sizeof(SPageFilePhysics), "acpmf_physics"
            )
            self._gfx_mmap = mmap.mmap(
                0, ctypes.sizeof(SPageFileGraphic), "acpmf_graphics"
            )
            self._static_mmap = mmap.mmap(
                0, ctypes.sizeof(SPageFileStatic), "acpmf_static"
            )

            self._physics = SPageFilePhysics.from_buffer(self._phys_mmap)
            self._graphics = SPageFileGraphic.from_buffer(self._gfx_mmap)
            self._static = SPageFileStatic.from_buffer(self._static_mmap)

            logger.info(
                "Connected to Assetto Corsa shared memory — "
                "Car: %s, Track: %s",
                self._static.carModel,
                self._static.track,
            )
            return True

        except (OSError, ValueError) as exc:
            logger.debug("AC shared memory not available yet: %s", exc)
            self._disconnect()
            return False

    def _disconnect(self) -> None:
        """Close all memory-mapped files safely."""
        for mm in (self._phys_mmap, self._gfx_mmap, self._static_mmap):
            if mm is not None:
                try:
                    mm.close()
                except Exception:
                    pass
        self._phys_mmap = None
        self._gfx_mmap = None
        self._static_mmap = None
        self._physics = None
        self._graphics = None
        self._static = None

    def _is_session_live(self) -> bool:
        """Check whether AC has an active (live/paused) session."""
        if self._graphics is None:
            return False
        return self._graphics.status in (self._STATUS_LIVE, self._STATUS_PAUSE)

    # ── Frame construction ───────────────────────────────────────────

    def _build_frame(self) -> TelemetryFrame | None:
        """Read current AC state and map it to a TelemetryFrame."""
        if self._physics is None or self._graphics is None or self._static is None:
            return None

        if not self._is_session_live():
            return None

        current_lap = self._graphics.completedLaps + 1
        fuel_kg = float(self._physics.fuel)

        # Track fuel consumption per lap.
        if current_lap != self._prev_lap and self._prev_fuel is not None and current_lap > 1:
            consumed = self._prev_fuel - fuel_kg
            if consumed > 0:
                self._fuel_per_lap_samples.append(consumed)
                # Keep a rolling window.
                if len(self._fuel_per_lap_samples) > 10:
                    self._fuel_per_lap_samples = self._fuel_per_lap_samples[-10:]

        self._prev_fuel = fuel_kg
        self._prev_lap = current_lap

        fuel_per_lap = (
            sum(self._fuel_per_lap_samples) / len(self._fuel_per_lap_samples)
            if self._fuel_per_lap_samples
            else self._fuel_per_lap_est
        )

        # Resolve total laps — prefer config override, fallback to AC session.
        total_laps = self._total_laps if self._total_laps > 0 else max(current_lap + 10, 20)

        # Try to get the tyre compound string.
        try:
            compound_str = self._physics.tyreCompound if hasattr(self._physics, "tyreCompound") else ""
        except (ValueError, AttributeError):
            compound_str = ""

        last_lap_sec = _parse_last_lap_ms(self._graphics.iLastTime)

        return TelemetryFrame(
            session_id=self._session_id,
            driver_id=self._driver_id,
            lap=current_lap,
            position=max(1, self._graphics.position),
            tire_compound=_map_tire_compound(str(compound_str)),
            tire_age=current_lap,  # Approximation — resets need pit detection.
            tire_wear_pct=_avg_tyre_wear_pct(self._physics.tyreWear),
            fuel_remaining_kg=round(fuel_kg, 1),
            fuel_per_lap_kg=round(fuel_per_lap, 2),
            gap_ahead_sec=None,  # AC doesn't expose gap via shared memory.
            gap_behind_sec=None,
            last_lap_time_sec=last_lap_sec,
            speed_kph=round(float(self._physics.speedKmh), 1),
            weather=_map_weather(float(self._physics.roadTemp)),
            track_temp_c=round(float(self._physics.roadTemp), 1),
            air_temp_c=round(float(self._physics.airTemp), 1),
            rain_chance_pct=0.0,
            total_laps=total_laps,
            timestamp=self._clock.now(),
        )

    # ── TelemetrySource interface ────────────────────────────────────

    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        """Yield telemetry frames from AC at ``interval_sec`` rate.

        If AC isn't running yet, waits and retries every 5 seconds.
        Automatically reconnects if the session drops.
        """
        logger.info(
            "Assetto Corsa telemetry source starting "
            "(poll interval: %.1fs)…",
            self._interval,
        )

        while not self._closed:
            # Wait for AC to be available.
            if self._physics is None:
                if not self._connect():
                    logger.info(
                        "Waiting for Assetto Corsa to start… "
                        "(retrying in 5s)"
                    )
                    await asyncio.sleep(5.0)
                    continue

            frame = self._build_frame()
            if frame is None:
                # Session not live — wait and retry.
                await asyncio.sleep(2.0)
                continue

            yield frame
            await asyncio.sleep(self._interval)

    async def close(self) -> None:
        """Signal the stream to stop and release shared memory."""
        self._closed = True
        self._disconnect()
        logger.info("Assetto Corsa telemetry source closed")
