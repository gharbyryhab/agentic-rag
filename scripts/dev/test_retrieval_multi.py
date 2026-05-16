"""Retrieval test on multiple questions to gauge diversity & precision.

Usage:
    python scripts/dev/test_retrieval_multi.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.embeddings import BgeEmbedder  # noqa: E402
from src.retrieval import Retriever  # noqa: E402
from src.vector_store import BM25Store, ChromaStore  # noqa: E402


QUESTIONS = [
    "What is overfitting in machine learning?",
    "How does backpropagation work?",
    "What is the difference between LoRA and full fine-tuning?",
    "Explain attention mechanism in transformers",
    "What is reinforcement learning?",
]


def main() -> None:
    r = Retriever(BgeEmbedder(), ChromaStore(), bm25=BM25Store())
    for q in QUESTIONS:
        print(f"\n--- {q}")
        for hit in r.retrieve(q, top_k=2):
            title = hit.metadata.get("book_title", "?")[:50]
            print(f"  [{hit.score:.3f}] {title}")


if __name__ == "__main__":
    main()
