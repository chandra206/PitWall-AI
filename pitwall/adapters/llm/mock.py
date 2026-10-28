"""Adapter: mock LLM client for testing and demos.

Returns deterministic, well-structured JSON responses that match what
the real models would produce, enabling full pipeline testing offline.
"""

from __future__ import annotations

import json

from pitwall.ports.llm import LLMClient


class MockLLMClient(LLMClient):
    """Fake LLM that returns canned responses for each model tier.

    Useful for:
    - Unit / integration tests without network.
    - Local development demos.
    - CI pipelines.
    """

    async def complete(self, prompt: str, *, model_tier: str = "nano") -> str:
        """Return a canned JSON response appropriate for the tier."""
        if model_tier == "nano":
            return self._nano_response(prompt)
        return self._ultra_response(prompt)

    @staticmethod
    def _nano_response(prompt: str) -> str:
        """Simulate a Nano triage response."""
        # Determine urgency from keywords in the prompt.
        is_critical = any(
            kw in prompt.lower()
            for kw in ("critical", "90%", "imminent", "fuel critical")
        )
        return json.dumps(
            {
                "priority_score": 0.9 if is_critical else 0.4,
                "needs_strategy": is_critical,
                "summary": "Alert assessed by mock Nano model",
                "reasoning": "Mock triage — severity keyword scan",
            }
        )

    @staticmethod
    def _ultra_response(prompt: str) -> str:
        """Simulate an Ultra strategy response with reasoning."""
        is_tire = "tire" in prompt.lower() or "tyre" in prompt.lower()
        action = "box_box" if is_tire else "stay_out"
        compound = "hard" if is_tire else None

        strategy = {
            "primary_action": action,
            "actions": [action],
            "confidence": 0.85,
            "reasoning": "Mock strategy — deterministic response for testing.",
            "pit_window_start": 25 if is_tire else None,
            "pit_window_end": 30 if is_tire else None,
            "recommended_compound": compound,
        }
        # Wrap in reasoning text to test JSON-in-content extraction.
        return (
            "Let me analyse the situation step by step.\n\n"
            "The telemetry indicates that action is needed.\n\n"
            f"```json\n{json.dumps(strategy, indent=2)}\n```\n\n"
            "This is the optimal strategy given current conditions."
        )
