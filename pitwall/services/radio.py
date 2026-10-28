"""Radio service — composes race-engineer messages and dispatches to TTS.

Receives ``StrategyComputed`` and ``RadioCallReady`` events, composes
natural-sounding radio messages, and sends them to the ``SpeechOutput``
port.
"""

from __future__ import annotations

from pitwall.domain.enums import PipelineStage, StrategyAction
from pitwall.domain.events import RadioCallReady, StrategyComputed
from pitwall.domain.models import RadioCall
from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector
from pitwall.ports.speech import SpeechOutput


# Natural-sounding templates keyed by strategy action.
_ACTION_TEMPLATES: dict[StrategyAction, str] = {
    StrategyAction.BOX_BOX: "Box box box! Pit this lap.",
    StrategyAction.PIT_NOW: "We need you in the pits now.",
    StrategyAction.PIT_NEXT_LAP: "Pit next lap, pit next lap.",
    StrategyAction.STAY_OUT: "Stay out, stay out. We're extending.",
    StrategyAction.EXTEND_STINT: "Extend the stint. Manage the tyres.",
    StrategyAction.PUSH: "Push now! Push push push!",
    StrategyAction.SAVE_TIRES: "Save the tyres. We need to make these last.",
    StrategyAction.DEFEND: "Defend position! Car behind is close.",
    StrategyAction.ATTACK: "Attack mode! Close the gap.",
}


class RadioService:
    """Compose and speak race-engineer radio messages.

    Handles two event types:
    - ``StrategyComputed``: compose a message from the strategy, then speak.
    - ``RadioCallReady``: speak a pre-composed message directly.
    """

    def __init__(
        self,
        speech: SpeechOutput,
        event_bus: EventBus,
        clock: Clock,
        logger: StructuredLogger,
        metrics: MetricsCollector,
    ) -> None:
        self._speech = speech
        self._bus = event_bus
        self._clock = clock
        self._logger = logger
        self._metrics = metrics

    async def handle_strategy(self, event: StrategyComputed) -> None:
        """Event handler: compose and speak a strategy recommendation."""
        strategy = event.strategy
        alert = event.original_alert

        message = self._compose_message(strategy.primary_action, strategy.reasoning)
        if strategy.recommended_compound is not None:
            message += f" Switch to {strategy.recommended_compound.value}s."

        call = RadioCall(
            correlation_id=strategy.correlation_id,
            message=message,
            priority=alert.severity,
            source_stage=PipelineStage.RADIO,
            timestamp=self._clock.now(),
        )

        await self._deliver(call)

    async def handle_radio_ready(self, event: RadioCallReady) -> None:
        """Event handler: speak a pre-composed radio call."""
        await self._deliver(event.radio_call)

    async def _deliver(self, call: RadioCall) -> None:
        """Log, speak, and record metrics for a radio call."""
        self._logger.info(
            f"Radio: {call.message}",
            correlation_id=call.correlation_id,
            stage=PipelineStage.RADIO.value,
            priority=call.priority.value,
        )
        self._metrics.increment("radio.calls_delivered")

        try:
            await self._speech.speak(call)
        except Exception as exc:
            self._logger.error(
                f"TTS delivery failed: {exc}",
                correlation_id=call.correlation_id,
                error=str(exc),
            )
            self._metrics.increment("radio.tts_errors")

    @staticmethod
    def _compose_message(action: StrategyAction, reasoning: str) -> str:
        """Build a natural-sounding radio message."""
        template = _ACTION_TEMPLATES.get(action, f"Strategy update: {action.value}.")
        # Append a brief reasoning excerpt if short enough.
        if len(reasoning) <= 80:
            return f"{template} {reasoning}"
        return template
