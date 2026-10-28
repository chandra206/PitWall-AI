"""Port interfaces — abstract contracts for everything that touches the outside world."""

from pitwall.ports.clock import Clock
from pitwall.ports.event_bus import EventBus
from pitwall.ports.llm import LLMClient
from pitwall.ports.logger import StructuredLogger
from pitwall.ports.metrics import MetricsCollector
from pitwall.ports.speech import SpeechOutput
from pitwall.ports.storage import Storage
from pitwall.ports.telemetry import TelemetrySource

__all__ = [
    "Clock",
    "EventBus",
    "LLMClient",
    "MetricsCollector",
    "SpeechOutput",
    "Storage",
    "StructuredLogger",
    "TelemetrySource",
]
