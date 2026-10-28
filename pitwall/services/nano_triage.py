"""Nano triage service — fast LLM-based alert classification.

Receives ``AlertRaised`` events, asks the Nano model to score priority
and decide whether the alert warrants deep strategy analysis, then
publishes ``AlertTriaged``.
"""

from __future__ import annotations

import json

from pitwall.domain.enums import AlertSeverity, PipelineStage
from pitwall.domain.events import AlertRaised, AlertTriaged, RadioCallReady
from pitwall.domain.models import Alert, RadioCall, TriageResult
from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.llm import LLMClient, LLMUnavailableError
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector


class NanoTriageService:
    """Score and classify alerts using the fast Nano model.

    If the LLM is unavailable, the service degrades gracefully:
    CRITICAL alerts are auto-escalated, others are logged and dropped.
    """

    def __init__(
        self,
        llm: LLMClient,
        event_bus: EventBus,
        clock: Clock,
        logger: StructuredLogger,
        metrics: MetricsCollector,
    ) -> None:
        self._llm = llm
        self._bus = event_bus
        self._clock = clock
        self._logger = logger
        self._metrics = metrics

    async def handle_alert(self, event: AlertRaised) -> None:
        """Event handler: triage an incoming alert."""
        alert = event.alert
        self._metrics.increment("nano.alerts_received")

        try:
            triage = await self._triage(alert)
        except LLMUnavailableError:
            self._logger.warning(
                "Nano model unavailable — falling back to severity-based triage",
                correlation_id=alert.correlation_id,
            )
            self._metrics.increment("nano.fallback_used")
            triage = self._fallback_triage(alert)

        self._logger.info(
            f"Triage complete: priority={triage.priority_score:.2f}, "
            f"needs_strategy={triage.needs_strategy}",
            correlation_id=alert.correlation_id,
            stage=PipelineStage.NANO_TRIAGE.value,
        )

        if triage.needs_strategy:
            await self._bus.publish(
                AlertTriaged(
                    triage=triage,
                    original_alert=alert,
                    correlation_id=alert.correlation_id,
                    timestamp=self._clock.now(),
                )
            )
        else:
            # Low-priority alerts get a direct canned radio call.
            radio_call = RadioCall(
                correlation_id=alert.correlation_id,
                message=f"Monitoring: {triage.summary}",
                priority=AlertSeverity.INFO,
                source_stage=PipelineStage.NANO_TRIAGE,
                timestamp=self._clock.now(),
            )
            await self._bus.publish(
                RadioCallReady(
                    radio_call=radio_call,
                    correlation_id=alert.correlation_id,
                    timestamp=self._clock.now(),
                )
            )

    async def _triage(self, alert: Alert) -> TriageResult:
        """Ask the Nano model to score and classify the alert."""
        prompt = self._build_prompt(alert)
        raw = await self._llm.complete(prompt, model_tier="nano")
        return self._parse_response(raw, alert)

    def _fallback_triage(self, alert: Alert) -> TriageResult:
        """Severity-based fallback when the model is unavailable."""
        needs_strategy = alert.severity == AlertSeverity.CRITICAL
        priority = 1.0 if needs_strategy else 0.5
        return TriageResult(
            alert_id=alert.id,
            correlation_id=alert.correlation_id,
            priority_score=priority,
            needs_strategy=needs_strategy,
            summary=alert.message,
            reasoning="Fallback: severity-based routing (Nano model unavailable)",
            timestamp=self._clock.now(),
        )

    @staticmethod
    def _build_prompt(alert: Alert) -> str:
        """Build the triage prompt with structured context."""
        frame = alert.telemetry_snapshot
        context = {
            "alert": {
                "severity": alert.severity.value,
                "rule": alert.rule_name,
                "message": alert.message,
            },
            "telemetry": {
                "lap": frame.lap,
                "position": frame.position,
                "tire_compound": frame.tire_compound.value,
                "tire_age": frame.tire_age,
                "tire_wear_pct": frame.tire_wear_pct,
                "fuel_remaining_kg": frame.fuel_remaining_kg,
                "gap_ahead_sec": frame.gap_ahead_sec,
                "gap_behind_sec": frame.gap_behind_sec,
                "weather": frame.weather.value,
                "rain_chance_pct": frame.rain_chance_pct,
                "total_laps": frame.total_laps,
            },
        }
        return (
            "You are an F1 race engineer AI assistant performing alert triage.\n"
            "Analyse the following alert and telemetry context.\n\n"
            f"```json\n{json.dumps(context, indent=2)}\n```\n\n"
            "Respond with ONLY a JSON object containing:\n"
            '- "priority_score": float 0.0-1.0 (1.0 = most urgent)\n'
            '- "needs_strategy": boolean (true if deep strategic analysis is needed)\n'
            '- "summary": one-sentence summary\n'
            '- "reasoning": brief explanation of your assessment\n'
        )

    def _parse_response(self, raw: str, alert: Alert) -> TriageResult:
        """Parse the Nano model's JSON response into a TriageResult."""
        try:
            # Handle markdown code fences if present.
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])
            data = json.loads(cleaned)
            return TriageResult(
                alert_id=alert.id,
                correlation_id=alert.correlation_id,
                priority_score=float(data.get("priority_score", 0.5)),
                needs_strategy=bool(data.get("needs_strategy", True)),
                summary=str(data.get("summary", alert.message)),
                reasoning=str(data.get("reasoning", "No reasoning provided")),
                timestamp=self._clock.now(),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self._logger.warning(
                f"Failed to parse Nano response, using fallback: {exc}",
                correlation_id=alert.correlation_id,
                raw_response=raw[:200],
            )
            self._metrics.increment("nano.parse_errors")
            return self._fallback_triage(alert)
