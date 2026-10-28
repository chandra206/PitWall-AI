"""Port: SpeechOutput — text-to-speech for radio calls."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pitwall.domain.models import RadioCall


class SpeechOutput(ABC):
    """Abstract speech output for delivering radio messages.

    Implementations may use browser Web Speech API, a cloud TTS service,
    or a null adapter that silently discards calls (useful in CI/testing).
    """

    @abstractmethod
    async def speak(self, call: RadioCall) -> None:
        """Speak the given radio call.

        Implementations should handle queuing if a previous utterance is
        still playing.  Must not raise on transient TTS errors — log and
        continue.
        """
        ...
