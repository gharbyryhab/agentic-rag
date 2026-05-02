"""Optional integration smoke test.

Skipped by default — requires the embedding model to be downloaded and a valid
Chroma installation. Run manually:

    pytest tests/integration -m integration --runxfail
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to enable.",
)


def test_index_and_query(tmp_path):
    from langchain_core.documents import Document

    from src.embeddings import BgeEmbedder
    from src.pipeline import IndexingPipeline
    from src.retrieval import Retriever
    from src.vector_store import ChromaStore

    # Tiny in-memory corpus
    docs = [
        Document(page_content="LoRA is a parameter-efficient fine-tuning method.",
                 metadata={"source": "doc1"}),
        Document(page_content="Transformers use self-attention to weigh tokens.",
                 metadata={"source": "doc2"}),
    ]

    embedder = BgeEmbedder(use_cache=False)
    store = ChromaStore()
    store.reset()

    pipe = IndexingPipeline(embedder=embedder, store=store)
    # Manually feed (skip loaders)
    from src.ingestion import chunk_documents
    chunks = chunk_documents(docs)
    texts = [c.page_content for c in chunks]
    metas = [pipe._sanitize_meta(c.metadata) for c in chunks]
    ids = [pipe._make_id(m) for m in metas]
    vectors = embedder.embed_documents(texts)
    store.add(ids, texts, vectors, metas)

    retriever = Retriever(embedder, store)
    results = retriever.retrieve("What is LoRA?", top_k=2)
    assert results
    assert any("LoRA" in r.text for r in results)
