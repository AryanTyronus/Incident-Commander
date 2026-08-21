from __future__ import annotations

import pytest

from backend.app.llm.fake import FakeLLMProvider
from backend.app.llm.interface import LLMProviderError
from backend.app.llm.ollama import OllamaProvider


class TestFakeLLMProvider:
    """Tests for FakeLLMProvider."""

    async def test_returns_preconfigured_response(self) -> None:
        provider = FakeLLMProvider(responses=["hello world"])
        result = await provider.generate("test")
        assert result == "hello world"

    async def test_returns_multiple_responses_in_order(self) -> None:
        provider = FakeLLMProvider(responses=["first", "second", "third"])
        assert await provider.generate("q1") == "first"
        assert await provider.generate("q2") == "second"
        assert await provider.generate("q3") == "third"

    async def test_records_calls(self) -> None:
        provider = FakeLLMProvider(responses=["ok1", "ok2"])
        await provider.generate("prompt1", system_prompt="sys1")
        await provider.generate("prompt2")

        assert provider.call_count == 2
        assert provider.calls[0]["prompt"] == "prompt1"
        assert provider.calls[0]["system_prompt"] == "sys1"
        assert provider.calls[1]["prompt"] == "prompt2"
        assert provider.calls[1]["system_prompt"] is None

    async def test_last_call(self) -> None:
        provider = FakeLLMProvider(responses=["a", "b"])
        assert provider.last_call() is None
        await provider.generate("first")
        assert provider.last_call() is not None
        assert provider.last_call()["prompt"] == "first"
        await provider.generate("second")
        assert provider.last_call()["prompt"] == "second"

    async def test_raises_when_no_responses(self) -> None:
        provider = FakeLLMProvider()
        with pytest.raises(LLMProviderError, match="No responses configured"):
            await provider.generate("test")

    async def test_raises_configured_error(self) -> None:
        provider = FakeLLMProvider(error=LLMProviderError("test error"))
        with pytest.raises(LLMProviderError, match="test error"):
            await provider.generate("test")

    async def test_health_check_healthy(self) -> None:
        provider = FakeLLMProvider(responses=["ok"])
        assert await provider.health_check() is True

    async def test_health_check_with_error(self) -> None:
        provider = FakeLLMProvider(error=LLMProviderError("down"))
        assert await provider.health_check() is False


class TestLLMProviderInterface:
    """Test that providers satisfy the LLMProvider protocol."""

    async def test_fake_satisfies_protocol(self) -> None:
        from backend.app.llm.interface import LLMProvider

        provider = FakeLLMProvider(responses=["test"])
        assert isinstance(provider, LLMProvider)

    def test_ollama_is_class(self) -> None:
        # OllamaProvider should be importable and instantiable
        # (we don't actually call it without Ollama)
        assert hasattr(OllamaProvider, "generate")
        assert hasattr(OllamaProvider, "health_check")


class TestOllamaProviderErrors:
    """Test OllamaProvider error handling with mocked HTTP."""

    def test_init_defaults(self) -> None:
        provider = OllamaProvider()
        assert provider._base_url == "http://localhost:11434"
        assert provider._model == "qwen3:8b"
        assert provider._timeout == 60

    def test_init_custom(self) -> None:
        provider = OllamaProvider(
            base_url="http://custom:9999",
            model="llama3",
            timeout=30,
        )
        assert provider._base_url == "http://custom:9999"
        assert provider._model == "llama3"
        assert provider._timeout == 30

    def test_init_strips_trailing_slash(self) -> None:
        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert provider._base_url == "http://localhost:11434"
