"""Anthropic provider: structured-output plan generation.

Uses ``client.messages.parse(..., output_format=ImplementationPlan)`` so the
model is constrained to our schema and the SDK validates the response into a
Pydantic object. All Anthropic-specific concerns stay in this file.

The SDK is an *optional* dependency (``codegraft[anthropic]``) and is imported
lazily, so the rest of codegraft — and the test suite — never requires it. Tests
inject a fake client; only real runs construct ``anthropic.Anthropic``.
"""

from __future__ import annotations

from typing import Any

from codegraft.config import Config
from codegraft.errors import PlanValidationError, ProviderError
from codegraft.models.plan import ImplementationPlan
from codegraft.providers.base import PlanningRequest, supports_temperature
from codegraft.providers.prompt import build_planning_prompt


class AnthropicProvider:
    """Generates plans via the Anthropic Messages API with structured outputs."""

    def __init__(self, config: Config, client: Any | None = None) -> None:
        self._config = config
        self._client = client  # injectable for tests; lazily created otherwise

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client

        key = self._config.secrets.anthropic_api_key
        if not key:
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Add it to your environment or a "
                ".env file (see `codegraft init`)."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise ProviderError(
                "The anthropic SDK is not installed. Install it with: "
                'pip install "codegraft[anthropic]"'
            ) from exc

        self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def generate_plan(self, request: PlanningRequest) -> ImplementationPlan:
        client = self._ensure_client()
        system, user = build_planning_prompt(request)

        model = self._config.provider.model
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": self._config.provider.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_format": ImplementationPlan,
        }
        temperature = self._config.provider.temperature
        if temperature is not None and supports_temperature(model):
            kwargs["temperature"] = temperature

        try:
            response = client.messages.parse(**kwargs)
        except PlanValidationError:
            raise
        except Exception as exc:  # wrap any SDK/transport error with context
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        plan = getattr(response, "parsed_output", None)
        if not isinstance(plan, ImplementationPlan):
            stop = getattr(response, "stop_reason", None)
            raise PlanValidationError(
                "Anthropic response did not parse into an ImplementationPlan"
                + (f" (stop_reason={stop})" if stop else "")
            )
        return plan
