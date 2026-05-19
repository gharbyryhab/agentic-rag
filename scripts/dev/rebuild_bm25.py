"""Rebuild the BM25 index from ChromaDB chunks (paginated to avoid SQLite limits)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.vector_store import BM25Store, ChromaStore
from src.utils import get_logger

log = get_logger("rebuild_bm25")

BATCH_SIZE = 1000


def main():
    chroma = ChromaStore()
    bm25 = BM25Store()

    total = chroma.count()
    log.info(f"ChromaDB has {total} chunks")
    log.info(f"BM25 currently has {bm25.count() if hasattr(bm25, 'count') else 'unknown'} entries")

    log.info(f"Loading all chunks from ChromaDB in batches of {BATCH_SIZE}...")
    all_ids: list[str] = []
    all_texts: list[str] = []
    all_metas: list[dict] = []

    for offset in range(0, total, BATCH_SIZE):
        batch = chroma.collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "metadatas"],
        )
        ids = batch["ids"]
        texts = batch["documents"]
        metas = batch["metadatas"] or [{}] * len(ids)
        all_ids.extend(ids)
        all_texts.extend(texts)
        all_metas.extend(metas)
        log.info(f"  Loaded {len(all_ids)}/{total}")

    log.info(f"Loaded {len(all_ids)} chunks from ChromaDB")

    log.info("Resetting BM25 store...")
    bm25.reset()

    log.info("Adding chunks to BM25 (tokenization + index build, may take a few minutes)...")
    bm25.add(ids=all_ids, texts=all_texts, metadatas=all_metas)

    final_count = bm25.count() if hasattr(bm25, 'count') else len(all_ids)
    log.info(f"Done. BM25 now has {final_count} entries")


if __name__ == "__main__":
    main()
