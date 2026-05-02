"""Smoke tests for the chunking module."""
from __future__ import annotations

from langchain_core.documents import Document

from src.ingestion import chunk_documents


def test_chunk_documents_produces_chunks():
    text = "Paragraph one.\n\n" + ("Lorem ipsum dolor sit amet. " * 200)
    doc = Document(page_content=text, metadata={"source": "fake.md"})

    chunks = chunk_documents([doc])

    assert len(chunks) > 1
    assert all(c.metadata["source"] == "fake.md" for c in chunks)
    assert all("chunk_index" in c.metadata for c in chunks)


def test_chunk_documents_handles_empty():
    chunks = chunk_documents([])
    assert chunks == []
