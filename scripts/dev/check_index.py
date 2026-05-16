"""Quick verification of the index state (ChromaDB + BM25 counts).

Usage:
    python scripts/dev/check_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script from anywhere
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.vector_store import ChromaStore, BM25Store  # noqa: E402


def main() -> None:
    c = ChromaStore()
    b = BM25Store()
    print(f"ChromaDB: {c.count()} chunks")
    try:
        print(f"BM25:     {b.count()} entries")
    except AttributeError:
        print("BM25:     loaded (no count method)")


if __name__ == "__main__":
    main()
