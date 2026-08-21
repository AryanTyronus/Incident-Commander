from __future__ import annotations

from pathlib import Path

from backend.app.retrieval.chroma import ChromaRetrieval
from backend.app.retrieval.embeddings import RetrievalResult
from backend.app.retrieval.indexer import DocumentIndexer


class RunbookSearch:
    """Semantic search over runbooks and postmortems.

    Provides a clean interface for agents to search documentation.
    """

    def __init__(
        self,
        retrieval: ChromaRetrieval,
        indexer: DocumentIndexer | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._indexer = indexer or DocumentIndexer()

    def index_runbooks(self, directory: str | Path) -> int:
        """Index all runbook documents from a directory."""
        chunks = self._indexer.index_directory(
            directory, document_type="runbook"
        )

        if not chunks:
            return 0

        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [c.chunk_id for c in chunks]

        self._retrieval.add_documents(documents, metadatas, ids)
        return len(chunks)

    def index_postmortems(self, directory: str | Path) -> int:
        """Index all postmortem documents from a directory."""
        chunks = self._indexer.index_directory(
            directory, document_type="postmortem"
        )

        if not chunks:
            return 0

        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [c.chunk_id for c in chunks]

        self._retrieval.add_documents(documents, metadatas, ids)
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        document_type: str | None = None,
    ) -> list[RetrievalResult]:
        """Search for relevant documentation."""
        where = None
        if document_type:
            where = {"document_type": document_type}

        return self._retrieval.query(query, n_results=top_k, where=where)
