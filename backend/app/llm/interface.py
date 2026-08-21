from __future__ import annotations

from typing import Protocol, runtime_checkable


class LLMProviderError(Exception):
    """Domain-specific error for LLM provider failures."""


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM request times out."""


class LLMConnectionError(LLMProviderError):
    """Raised when an LLM connection fails."""


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract interface for LLM providers.

    The commander depends on this protocol, never on a concrete provider.
    """

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt for context.

        Returns:
            The generated text response.

        Raises:
            LLMProviderError: On provider-level failures.
        """
        ...

    async def health_check(self) -> bool:
        """Check if the LLM provider is available.

        Returns:
            True if the provider is reachable and healthy.
        """
        ...
