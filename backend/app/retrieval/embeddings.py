from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors."""
        ...

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...


class FakeEmbeddingProvider:
    """Deterministic fake embedding provider for testing.

    Produces consistent embeddings based on text content.
    No model download required.
    """

    def __init__(self, dim: int = 128) -> None:
        self._dim = dim

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate deterministic pseudo-embeddings."""
        results: list[list[float]] = []
        for text in texts:
            # Create a deterministic vector from text hash
            seed = hash(text) % (2**32)
            import random

            rng = random.Random(seed)
            vec = [rng.gauss(0, 1) for _ in range(self._dim)]
            # Normalize
            norm = sum(v**2 for v in vec) ** 0.5
            if norm > 0:
                vec = [v / norm for v in vec]
            results.append(vec)
        return results


class OllamaEmbeddingProvider:
    """Embedding provider using Ollama's embedding API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ) -> None:
        self._base_url = base_url
        self._model = model
        self._dim = 768  # Default for nomic-embed-text

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using Ollama API."""
        import httpx

        results: list[list[float]] = []
        with httpx.Client(timeout=30) as client:
            for text in texts:
                resp = client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                results.append(data["embedding"])
        return results


@dataclass
class RetrievalResult:
    """A single retrieval result from semantic search."""

    document_id: str
    chunk_id: str
    text: str
    similarity: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentChunk:
    """A chunk of a document ready for indexing."""

    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
