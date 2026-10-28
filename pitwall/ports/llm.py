"""Port: LLMClient — language-model completions for triage and strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract client for LLM completions.

    The ``model_tier`` parameter selects the model size/cost tradeoff:
    ``"nano"`` for fast triage, ``"ultra"`` for deep strategic reasoning.
    Implementations must handle timeouts, retries, and circuit-breaking
    internally (or delegate to infrastructure wrappers).
    """

    @abstractmethod
    async def complete(self, prompt: str, *, model_tier: str = "nano") -> str:
        """Send a prompt and return the raw completion text.

        Args:
            prompt: The fully-formatted prompt string.
            model_tier: Which model tier to use (``"nano"`` or ``"ultra"``).

        Returns:
            The model's completion as a plain string.

        Raises:
            LLMUnavailableError: If the model cannot be reached after retries.
        """
        ...


class LLMUnavailableError(Exception):
    """Raised when no LLM backend can service the request."""
