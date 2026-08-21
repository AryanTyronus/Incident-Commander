from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.app.retrieval.embeddings import (
    EmbeddingProvider,
    RetrievalResult,
)


class ChromaRetrieval:
    """ChromaDB-based semantic retrieval layer.

    Wraps ChromaDB for document storage and semantic search.
    Uses local persistent storage by default.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "runbooks",
        persist_directory: str | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._collection_name = collection_name
        self._persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIRECTORY",
            str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "chroma"),
        )
        self._client = None
        self._collection = None

    def _ensure_initialized(self) -> None:
        """Lazily initialize ChromaDB client and collection."""
        if self._collection is not None:
            return

        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
        except ImportError:
            raise ImportError(
                "chromadb is required for retrieval. Install with: pip install chromadb"
            )

        Path(self._persist_directory).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self._persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        """Add documents to the collection."""
        self._ensure_initialized()

        if not documents:
            return

        embeddings = self._embedding_provider.embed(documents)

        self._collection.add(  # type: ignore[union-attr]
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Query the collection for similar documents."""
        self._ensure_initialized()

        query_embedding = self._embedding_provider.embed([query_text])[0]

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)  # type: ignore[union-attr]

        retrieval_results: list[RetrievalResult] = []

        if results and results.get("documents"):
            docs = results["documents"][0] if results["documents"] else []
            metas = results["metadatas"][0] if results.get("metadatas") else []
            ids = results["ids"][0] if results.get("ids") else []
            distances = (
                results["distances"][0] if results.get("distances") else []
            )

            for i, doc in enumerate(docs):
                distance = distances[i] if i < len(distances) else 0.0
                # Convert cosine distance to similarity
                similarity = 1.0 - distance

                meta = metas[i] if i < len(metas) else {}
                chunk_id = ids[i] if i < len(ids) else ""
                # Use document_id from metadata, fall back to chunk_id
                doc_id = meta.get("document_id", chunk_id)

                retrieval_results.append(
                    RetrievalResult(
                        document_id=doc_id,
                        chunk_id=chunk_id,
                        text=doc,
                        similarity=similarity,
                        metadata=meta,
                    )
                )

        return retrieval_results

    def delete_document(self, document_id: str) -> None:
        """Delete all chunks for a document."""
        self._ensure_initialized()
        self._collection.delete(  # type: ignore[union-attr]
            where={"document_id": document_id}
        )

    def count(self) -> int:
        """Return the number of documents in the collection."""
        self._ensure_initialized()
        return self._collection.count()  # type: ignore[union-attr]

    def reset(self) -> None:
        """Reset the collection (for testing)."""
        if self._client is not None:
            try:
                self._client.delete_collection(self._collection_name)
            except Exception:
                pass
            self._collection = None
