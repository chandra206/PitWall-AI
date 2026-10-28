"""Adapter: Nebius-hosted LLM client with circuit breaker and retry.

Wraps the OpenAI-compatible Nebius Studio API using ``httpx``.
"""

from __future__ import annotations

import json

import httpx

from pitwall.infra.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from pitwall.infra.retry import RetryExhausted, retry_with_backoff
from pitwall.ports.llm import LLMClient, LLMUnavailableError


class NebiusLLMClient(LLMClient):
    """Production LLM client targeting the Nebius Studio API.

    Uses circuit-breaker wrapping and retry-with-backoff on every call.
    Model selection is driven by the ``model_tier`` parameter.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.studio.nebius.com/v1",
        nano_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
        ultra_model: str = "deepseek-ai/DeepSeek-R1",
        timeout_sec: float = 30.0,
        max_retries: int = 3,
        cb_failure_threshold: int = 5,
        cb_recovery_timeout_sec: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._models = {"nano": nano_model, "ultra": ultra_model}
        self._timeout = timeout_sec
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_sec),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        self._breaker = CircuitBreaker(
            failure_threshold=cb_failure_threshold,
            recovery_timeout_sec=cb_recovery_timeout_sec,
        )

    async def complete(self, prompt: str, *, model_tier: str = "nano") -> str:
        """Send a chat completion request to Nebius.

        Raises:
            LLMUnavailableError: On circuit-breaker open or exhausted retries.
        """
        model = self._models.get(model_tier, self._models["nano"])

        try:
            return await retry_with_backoff(
                self._call,
                prompt,
                model,
                max_retries=self._max_retries,
                retryable_exceptions=(httpx.HTTPStatusError, httpx.TransportError),
            )
        except (RetryExhausted, CircuitBreakerOpen) as exc:
            raise LLMUnavailableError(str(exc)) from exc

    async def _call(self, prompt: str, model: str) -> str:
        """Single attempt — wrapped by retry and circuit breaker."""
        async with self._breaker:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                content=json.dumps(payload),
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
