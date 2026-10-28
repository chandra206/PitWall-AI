"""Reflex engine — evaluates all registered rules and publishes alerts.

The engine is the only component that turns an ``AlertSpec`` (pure output
from a rule function) into a full ``Alert`` enriched with IDs, timestamps,
and telemetry context.  It also deduplicates alerts so the same condition
on the same lap doesn't fire twice.
"""

from __future__ import annotations

from pitwall.domain.enums import PipelineStage
from pitwall.domain.events import AlertRaised
from pitwall.domain.models import Alert, TelemetryFrame
from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector
from pitwall.services.reflex.registry import RuleRegistry


class ReflexEngine:
    """Evaluate registered rules against each telemetry frame.

    Pure rules return ``AlertSpec | None``.  This engine:
    1. Calls each rule with the frame.
    2. Deduplicates by ``(rule_name, severity, lap)``.
    3. Enriches the spec into a full ``Alert`` (timestamp from Clock, IDs).
    4. Publishes ``AlertRaised`` on the event bus.
    """

    def __init__(
        self,
        registry: RuleRegistry,
        event_bus: EventBus,
        clock: Clock,
        logger: StructuredLogger,
        metrics: MetricsCollector,
    ) -> None:
        self._registry = registry
        self._bus = event_bus
        self._clock = clock
        self._logger = logger
        self._metrics = metrics
        self._seen: set[str] = set()

    async def evaluate(self, frame: TelemetryFrame) -> list[Alert]:
        """Run all rules against *frame* and return new alerts."""
        alerts: list[Alert] = []

        for name, rule_fn in self._registry.rules.items():
            try:
                spec = rule_fn(frame)
            except Exception as exc:
                self._logger.error(
                    f"Rule '{name}' raised unexpectedly",
                    rule=name,
                    error=str(exc),
                )
                self._metrics.increment("reflex.rule_errors", rule=name)
                continue

            if spec is None:
                continue

            dedup_key = f"{spec.rule_name}:{spec.severity.value}:{frame.lap}"
            if dedup_key in self._seen:
                self._metrics.increment("reflex.deduped", rule=name)
                continue
            self._seen.add(dedup_key)

            alert = Alert(
                severity=spec.severity,
                source_stage=PipelineStage.REFLEX,
                rule_name=spec.rule_name,
                message=spec.message,
                telemetry_snapshot=frame,
                timestamp=self._clock.now(),
            )
            alerts.append(alert)

            self._logger.info(
                f"Alert raised: {alert.message}",
                correlation_id=alert.correlation_id,
                rule=name,
                severity=alert.severity.value,
                lap=frame.lap,
            )
            self._metrics.increment("reflex.alerts_raised", rule=name)

            await self._bus.publish(
                AlertRaised(
                    alert=alert,
                    correlation_id=alert.correlation_id,
                    timestamp=self._clock.now(),
                )
            )

        return alerts

    def clear_dedup_cache(self) -> None:
        """Clear deduplication state (e.g. at session start)."""
        self._seen.clear()
