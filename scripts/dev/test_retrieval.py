"""Quick retrieval test on a single question.

Usage:
    python scripts/dev/test_retrieval.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.embeddings import BgeEmbedder  # noqa: E402
from src.retrieval import Retriever  # noqa: E402
from src.vector_store import BM25Store, ChromaStore  # noqa: E402


def main() -> None:
    r = Retriever(BgeEmbedder(), ChromaStore(), bm25=BM25Store())
    question = "What is overfitting in machine learning?"
    print(f"\nQuery: {question}\n")
    print("=" * 70)
    for hit in r.retrieve(question, top_k=3):
        title = hit.metadata.get("book_title", "?")[:50]
        print(f"  [score={hit.score:.3f}]  {title}")
        print(f"    {hit.text[:150]}...")
        print()


if __name__ == "__main__":
    main()
