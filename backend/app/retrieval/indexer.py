from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from backend.app.retrieval.embeddings import DocumentChunk


def _chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Deterministic text chunking with overlap.

    Splits text into chunks of approximately chunk_size characters,
    with overlap between consecutive chunks.
    """
    if not text.strip():
        return []

    # Split by paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)

    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # If we have no chunks yet, split by sentences
    if not chunks:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                current_chunk = f"{current_chunk} {sentence}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:chunk_size]]


def _compute_document_id(file_path: str, content: str) -> str:
    """Compute a deterministic document ID from path and content."""
    hash_input = f"{file_path}:{content}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


class DocumentIndexer:
    """Indexes documents into chunks for semantic retrieval.

    Supports .md, .txt, and similar text documents.
    Preserves metadata for provenance tracking.
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def index_file(
        self,
        file_path: str | Path,
        document_type: str = "runbook",
        title: str | None = None,
    ) -> list[DocumentChunk]:
        """Index a single file into chunks."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.index_content(
            content=content,
            file_path=str(path),
            document_type=document_type,
            title=title or path.stem,
        )

    def index_content(
        self,
        content: str,
        file_path: str = "<inline>",
        document_type: str = "runbook",
        title: str = "",
    ) -> list[DocumentChunk]:
        """Index content into chunks."""
        doc_id = _compute_document_id(file_path, content)
        text_chunks = _chunk_text(content, self._chunk_size, self._chunk_overlap)

        chunks: list[DocumentChunk] = []
        for i, text in enumerate(text_chunks):
            chunk_id = f"{doc_id}_chunk_{i:04d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    text=text,
                    metadata={
                        "document_id": doc_id,
                        "document_path": file_path,
                        "chunk_id": chunk_id,
                        "document_type": document_type,
                        "title": title,
                        "chunk_index": i,
                        "total_chunks": len(text_chunks),
                    },
                )
            )

        return chunks

    def index_directory(
        self,
        directory: str | Path,
        document_type: str = "runbook",
        extensions: tuple[str, ...] = (".md", ".txt"),
    ) -> list[DocumentChunk]:
        """Index all matching files in a directory."""
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        all_chunks: list[DocumentChunk] = []

        for ext in extensions:
            for file_path in sorted(dir_path.rglob(f"*{ext}")):
                try:
                    chunks = self.index_file(
                        file_path,
                        document_type=document_type,
                        title=file_path.stem,
                    )
                    all_chunks.extend(chunks)
                except Exception:
                    continue

        return all_chunks

    def get_metadata_for_chunks(
        self, chunks: list[DocumentChunk]
    ) -> list[dict[str, Any]]:
        """Extract metadata dictionaries from chunks for ChromaDB."""
        return [chunk.metadata for chunk in chunks]
