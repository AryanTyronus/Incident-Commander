#!/usr/bin/env python3
"""Optional smoke test for Ollama connectivity.

This script is NOT part of the deterministic test suite.
It requires a running Ollama server and network access.

Usage:
    python scripts/smoke_ollama.py
"""

import asyncio
import sys

sys.path.insert(0, ".")

from backend.app.llm.interface import LLMProviderError
from backend.app.llm.ollama import OllamaProvider


async def main() -> int:
    print("Checking Ollama availability...")

    provider = OllamaProvider()

    # Health check
    healthy = await provider.health_check()
    if not healthy:
        print("ERROR: Ollama is not reachable")
        print("Make sure Ollama is running: ollama serve")
        return 1

    print("Ollama is reachable")

    # Simple generation test
    print(f"Model: {provider._model}")
    print("Sending test prompt...")

    try:
        response = await provider.generate(
            "Say 'Hello from Incident Commander' and nothing else.",
            system_prompt="You are a test assistant. Be brief.",
        )
        print(f"Response: {response.strip()}")
        print("Smoke test passed!")
        return 0
    except LLMProviderError as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
