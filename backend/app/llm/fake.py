from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.app.llm.interface import LLMProviderError


@dataclass
class FakeLLMProvider:
    """Deterministic fake LLM provider for testing.

    Records all calls and returns pre-configured responses in order.
    """

    responses: list[str] = field(default_factory=list)
    error: LLMProviderError | None = None
    _calls: list[dict[str, Any]] = field(default_factory=list, repr=False)

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Record the call and return the next configured response."""
        self._calls.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
        })

        if self.error is not None:
            raise self.error

        if not self.responses:
            raise LLMProviderError("No responses configured in FakeLLMProvider")

        return self.responses.pop(0)

    async def health_check(self) -> bool:
        """Always healthy unless configured with an error."""
        return self.error is None

    @property
    def call_count(self) -> int:
        """Number of generate() calls made."""
        return len(self._calls)

    @property
    def calls(self) -> list[dict[str, Any]]:
        """Copy of all recorded calls."""
        return list(self._calls)

    def last_call(self) -> dict[str, Any] | None:
        """Return the most recent call, or None."""
        return self._calls[-1] if self._calls else None
