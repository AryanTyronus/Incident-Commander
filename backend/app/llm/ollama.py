from __future__ import annotations

import httpx

from backend.app.config import settings
from backend.app.llm.interface import LLMConnectionError, LLMProviderError, LLMTimeoutError


class OllamaProvider:
    """LLM provider that communicates with a local Ollama server."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.OLLAMA_MODEL
        self._timeout = timeout or settings.OLLAMA_TIMEOUT

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        """Generate a response from Ollama."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(
                f"Ollama request timed out after {self._timeout}s"
            ) from e
        except httpx.ConnectError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self._base_url}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise LLMProviderError(
                f"Ollama returned HTTP {e.response.status_code}"
            ) from e
        except Exception as e:
            raise LLMProviderError(
                f"Ollama request failed: {type(e).__name__}"
            ) from e

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
