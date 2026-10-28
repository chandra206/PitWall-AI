"""Ultra strategist service — deep strategic reasoning via the reasoning model.

Receives ``AlertTriaged`` events (only high-priority ones that passed Nano
triage), sends a rich prompt to the Ultra model (e.g. DeepSeek-R1), parses
the structured strategy response, and publishes ``StrategyComputed``.

Uses the **JSON-in-content** approach: the model is prompted to embed its
structured output as a JSON block inside its natural-language reasoning.
This works better with reasoning models that resist strict output schemas.
"""

from __future__ import annotations

import json

from pitwall.domain.enums import (
    AlertSeverity,
    PipelineStage,
    StrategyAction,
    TireCompound,
)
from pitwall.domain.events import AlertTriaged, RadioCallReady, StrategyComputed
from pitwall.domain.models import (
    Alert,
    RadioCall,
    StrategyRecommendation,
    TriageResult,
)
from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.llm import LLMClient, LLMUnavailableError
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector


class UltraStrategistService:
    """Produce race strategy recommendations using the Ultra reasoning model.

    If the model is unavailable, the service degrades to canned strategies
    based on the alert severity and rule, ensuring the driver always gets
    actionable guidance.
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

    async def handle_triaged(self, event: AlertTriaged) -> None:
        """Event handler: produce strategy for a triaged alert."""
        alert = event.original_alert
        triage = event.triage
        self._metrics.increment("ultra.requests_received")

        try:
            strategy = await self._strategize(alert, triage)
        except LLMUnavailableError:
            self._logger.warning(
                "Ultra model unavailable — using canned strategy",
                correlation_id=alert.correlation_id,
            )
            self._metrics.increment("ultra.fallback_used")
            strategy = self._fallback_strategy(alert)

        self._logger.info(
            f"Strategy computed: {strategy.primary_action.value} "
            f"(confidence={strategy.confidence:.2f})",
            correlation_id=alert.correlation_id,
            stage=PipelineStage.ULTRA_STRATEGIST.value,
        )

        await self._bus.publish(
            StrategyComputed(
                strategy=strategy,
                original_alert=alert,
                correlation_id=alert.correlation_id,
                timestamp=self._clock.now(),
            )
        )

    async def _strategize(
        self, alert: Alert, triage: TriageResult
    ) -> StrategyRecommendation:
        """Ask the Ultra model for a deep strategy analysis."""
        prompt = self._build_prompt(alert, triage)
        raw = await self._llm.complete(prompt, model_tier="ultra")
        return self._parse_response(raw, alert)

    def _fallback_strategy(self, alert: Alert) -> StrategyRecommendation:
        """Rule-based fallback when the model is unavailable."""
        action_map: dict[str, StrategyAction] = {
            "tire_degradation": StrategyAction.BOX_BOX,
            "fuel_critical": StrategyAction.SAVE_TIRES,
            "weather_change": StrategyAction.PIT_NOW,
            "gap_alert": StrategyAction.DEFEND,
        }
        action = action_map.get(alert.rule_name, StrategyAction.STAY_OUT)
        return StrategyRecommendation(
            correlation_id=alert.correlation_id,
            actions=(action,),
            primary_action=action,
            reasoning=f"Canned fallback for {alert.rule_name} (Ultra model unavailable)",
            confidence=0.5,
            timestamp=self._clock.now(),
        )

    @staticmethod
    def _build_prompt(alert: Alert, triage: TriageResult) -> str:
        """Build the strategy prompt with full race context."""
        frame = alert.telemetry_snapshot
        context = {
            "alert": {
                "severity": alert.severity.value,
                "rule": alert.rule_name,
                "message": alert.message,
            },
            "triage": {
                "priority_score": triage.priority_score,
                "summary": triage.summary,
                "reasoning": triage.reasoning,
            },
            "telemetry": {
                "lap": frame.lap,
                "total_laps": frame.total_laps,
                "position": frame.position,
                "tire_compound": frame.tire_compound.value,
                "tire_age": frame.tire_age,
                "tire_wear_pct": frame.tire_wear_pct,
                "fuel_remaining_kg": frame.fuel_remaining_kg,
                "fuel_per_lap_kg": frame.fuel_per_lap_kg,
                "gap_ahead_sec": frame.gap_ahead_sec,
                "gap_behind_sec": frame.gap_behind_sec,
                "last_lap_time_sec": frame.last_lap_time_sec,
                "weather": frame.weather.value,
                "rain_chance_pct": frame.rain_chance_pct,
                "track_temp_c": frame.track_temp_c,
            },
        }
        return (
            "You are an elite F1 chief strategist AI.\n"
            "Analyse the alert, triage assessment, and full telemetry below.\n\n"
            f"```json\n{json.dumps(context, indent=2)}\n```\n\n"
            "Reason step by step about the optimal strategy, then include "
            "a JSON block in your response with exactly these fields:\n"
            '- "primary_action": one of [pit_now, pit_next_lap, extend_stint, '
            "push, save_tires, box_box, stay_out, defend, attack]\n"
            '- "actions": array of actions in priority order\n'
            '- "confidence": float 0.0-1.0\n'
            '- "reasoning": one-paragraph strategic rationale\n'
            '- "pit_window_start": lap number or null\n'
            '- "pit_window_end": lap number or null\n'
            '- "recommended_compound": tire compound or null\n'
        )

    def _parse_response(
        self, raw: str, alert: Alert
    ) -> StrategyRecommendation:
        """Extract the JSON strategy block from the model's reasoning output."""
        try:
            # Find JSON block in the response (JSON-in-content pattern).
            json_str = self._extract_json_block(raw)
            data = json.loads(json_str)

            actions_raw = data.get("actions", [data.get("primary_action", "stay_out")])
            actions = tuple(StrategyAction(a) for a in actions_raw)

            compound_raw = data.get("recommended_compound")
            compound = TireCompound(compound_raw) if compound_raw else None

            return StrategyRecommendation(
                correlation_id=alert.correlation_id,
                actions=actions if actions else (StrategyAction.STAY_OUT,),
                primary_action=StrategyAction(
                    data.get("primary_action", "stay_out")
                ),
                reasoning=str(
                    data.get("reasoning", "No reasoning extracted")
                ),
                confidence=float(data.get("confidence", 0.5)),
                pit_window_start=data.get("pit_window_start"),
                pit_window_end=data.get("pit_window_end"),
                recommended_compound=compound,
                timestamp=self._clock.now(),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            self._logger.warning(
                f"Failed to parse Ultra response: {exc}",
                correlation_id=alert.correlation_id,
                raw_response=raw[:300],
            )
            self._metrics.increment("ultra.parse_errors")
            return self._fallback_strategy(alert)

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Extract the first JSON object from text, handling code fences."""
        # Try to find a fenced code block first.
        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:  # odd-indexed parts are inside fences
                content = part.strip()
                if content.startswith("json"):
                    content = content[4:].strip()
                if content.startswith("{"):
                    return content

        # Fall back to finding raw { ... }.
        start = text.find("{")
        if start == -1:
            msg = "No JSON object found in response"
            raise json.JSONDecodeError(msg, text, 0)

        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        msg = "Unclosed JSON object in response"
        raise json.JSONDecodeError(msg, text, start)
