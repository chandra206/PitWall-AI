"""12-factor configuration validated at startup via Pydantic Settings.

All values come from environment variables (prefixed ``PITWALL_``).
Secrets are **never** logged; they exist only in the process environment.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PitWallConfig(BaseSettings):
    """Central, validated configuration for the entire application."""

    model_config = SettingsConfigDict(
        env_prefix="PITWALL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telemetry ────────────────────────────────────────────
    telemetry_source: str = "simulator"  # simulator | csv_replay | assetto_corsa
    telemetry_csv_path: str | None = None
    telemetry_interval_sec: float = Field(default=1.0, gt=0)

    # ── Assetto Corsa ────────────────────────────────────────
    ac_total_laps: int = Field(default=0, ge=0)  # 0 = auto-detect
    ac_fuel_per_lap_estimate: float = Field(default=2.5, gt=0)

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: str = "mock"
    llm_api_key: str = Field(default="", repr=False)  # repr=False hides from logs
    llm_api_base_url: str = "https://api.studio.nebius.com/v1"
    llm_nano_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    llm_ultra_model: str = "deepseek-ai/DeepSeek-R1"
    llm_timeout_sec: float = Field(default=30.0, gt=0)
    llm_max_retries: int = Field(default=3, ge=0)

    # ── Speech ───────────────────────────────────────────────
    speech_provider: str = "null"

    # ── Event Bus ────────────────────────────────────────────
    bus_telemetry_queue_size: int = Field(default=100, gt=0)
    bus_alert_queue_size: int = Field(default=1000, gt=0)

    # ── Circuit Breaker ──────────────────────────────────────
    cb_failure_threshold: int = Field(default=5, gt=0)
    cb_recovery_timeout_sec: float = Field(default=60.0, gt=0)
    cb_half_open_max_calls: int = Field(default=1, gt=0)

    # ── Storage ──────────────────────────────────────────────
    storage_path: str = "./data"

    # ── Logging ──────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "json"

    # ── Session ──────────────────────────────────────────────
    driver_id: str = "driver_01"
    session_id: str = "session_01"
    total_laps: int = Field(default=57, gt=0)
