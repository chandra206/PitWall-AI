"""Adapter: null speech output — silently discards all radio calls.

Used in CI, headless tests, and any context where TTS is not desired.
"""

from __future__ import annotations

from pitwall.domain.models import RadioCall
from pitwall.ports.speech import SpeechOutput


class NullSpeechOutput(SpeechOutput):
    """No-op speech adapter that silently discards radio calls."""

    async def speak(self, call: RadioCall) -> None:
        """Do nothing."""
