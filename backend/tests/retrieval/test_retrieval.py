from __future__ import annotations

import tempfile
from pathlib import Path

from backend.app.retrieval.chroma import ChromaRetrieval
from backend.app.retrieval.embeddings import FakeEmbeddingProvider
from backend.app.retrieval.indexer import DocumentIndexer
from backend.app.tools.runbook_search import RunbookSearch


class TestChromaRetrieval:
    """Tests for ChromaDB retrieval layer."""

    def setup_method(self) -> None:
        self.provider = FakeEmbeddingProvider()
        self.tmp_dir = tempfile.mkdtemp()
        self.retrieval = ChromaRetrieval(
            embedding_provider=self.provider,
            collection_name="test_runbooks",
            persist_directory=self.tmp_dir,
        )

    def test_add_and_query(self) -> None:
        self.retrieval.add_documents(
            documents=["How to handle payment failures", "Database error resolution"],
            metadatas=[
                {"document_type": "runbook", "title": "Payment Failures"},
                {"document_type": "runbook", "title": "Database Errors"},
            ],
            ids=["doc1", "doc2"],
        )

        results = self.retrieval.query("payment issues")
        assert len(results) > 0
        assert results[0].document_id in ("doc1", "doc2")

    def test_query_empty_collection(self) -> None:
        results = self.retrieval.query("anything")
        assert len(results) == 0

    def test_count(self) -> None:
        assert self.retrieval.count() == 0

        self.retrieval.add_documents(
            documents=["doc1"],
            metadatas=[{"document_type": "runbook"}],
            ids=["id1"],
        )

        assert self.retrieval.count() == 1

    def test_delete_document(self) -> None:
        self.retrieval.add_documents(
            documents=["doc1", "doc2"],
            metadatas=[
                {"document_type": "runbook", "document_id": "doc1"},
                {"document_type": "runbook", "document_id": "doc2"},
            ],
            ids=["id1", "id2"],
        )

        self.retrieval.delete_document("doc1")
        assert self.retrieval.count() == 1


class TestDocumentIndexer:
    """Tests for document indexing."""

    def setup_method(self) -> None:
        self.indexer = DocumentIndexer(chunk_size=200, chunk_overlap=20)

    def test_index_content(self) -> None:
        content = "# Payment Failures\n\nThis is a runbook about payment failures."
        chunks = self.indexer.index_content(content, "test.md", "runbook", "Payment")

        assert len(chunks) > 0
        assert chunks[0].metadata["document_type"] == "runbook"
        assert chunks[0].metadata["title"] == "Payment"
        assert chunks[0].metadata["document_path"] == "test.md"

    def test_chunk_metadata(self) -> None:
        content = "Line 1\n\nLine 2\n\nLine 3"
        chunks = self.indexer.index_content(content)

        assert len(chunks) > 0
        for chunk in chunks:
            assert "document_id" in chunk.metadata
            assert "chunk_id" in chunk.metadata
            assert "chunk_index" in chunk.metadata

    def test_deterministic_chunking(self) -> None:
        content = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        chunks1 = self.indexer.index_content(content)
        chunks2 = self.indexer.index_content(content)

        assert len(chunks1) == len(chunks2)
        for c1, c2 in zip(chunks1, chunks2):
            assert c1.text == c2.text
            assert c1.document_id == c2.document_id

    def test_index_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Document\n\nSome content here.")
            f.flush()
            path = f.name

        chunks = self.indexer.index_file(path, "runbook", "Test")
        assert len(chunks) > 0
        assert chunks[0].metadata["title"] == "Test"

    def test_empty_content(self) -> None:
        chunks = self.indexer.index_content("")
        # Should handle gracefully
        assert isinstance(chunks, list)


class TestRunbookSearch:
    """Tests for runbook search tool."""

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.provider = FakeEmbeddingProvider()
        self.retrieval = ChromaRetrieval(
            embedding_provider=self.provider,
            collection_name="test_search",
            persist_directory=self.tmp_dir,
        )
        self.indexer = DocumentIndexer()
        self.search = RunbookSearch(self.retrieval, self.indexer)

    def test_index_and_search(self) -> None:
        runbooks_dir = (
            Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "runbooks"
        )
        count = self.search.index_runbooks(runbooks_dir)
        assert count > 0

        results = self.search.search("payment failures", top_k=3)
        assert len(results) > 0

    def test_search_empty(self) -> None:
        results = self.search.search("payment")
        assert len(results) == 0
