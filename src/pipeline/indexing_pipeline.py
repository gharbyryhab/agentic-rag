"""End-to-end indexing : raw files -> chunks -> embeddings -> ChromaDB."""
from __future__ import annotations

import uuid
from pathlib import Path

from tqdm import tqdm

from src.embeddings import BgeEmbedder
from src.ingestion import chunk_documents, load_documents
from src.utils import get_logger
from src.vector_store import ChromaStore

log = get_logger(__name__)

# Process embeddings + DB writes in slices so progress is visible and a crash
# mid-run doesn't lose everything (already-embedded chunks are persisted).
_INDEX_BATCH = 256


class IndexingPipeline:
    def __init__(
        self,
        embedder: BgeEmbedder | None = None,
        store: ChromaStore | None = None,
    ) -> None:
        self.embedder = embedder or BgeEmbedder()
        self.store = store or ChromaStore()

    def run(
        self,
        source: str | Path,
        reset: bool = False,
        limit: int | None = None,
    ) -> dict[str, int]:
        if reset:
            self.store.reset()

        docs = load_documents(source)
        if not docs:
            log.warning(f"No documents found at {source}")
            return {"docs": 0, "chunks": 0, "indexed": 0}

        chunks = chunk_documents(docs)
        if not chunks:
            return {"docs": len(docs), "chunks": 0, "indexed": 0}

        # Drop chunks that became empty after cleaning
        chunks = [c for c in chunks if c.page_content and c.page_content.strip()]

        if limit is not None:
            chunks = chunks[:limit]
            log.info(f"--limit applied : keeping {len(chunks)} chunks")

        texts = [c.page_content for c in chunks]
        metadatas = [self._sanitize_meta(c.metadata) for c in chunks]
        ids = [self._make_id(m) for m in metadatas]

        log.info(f"Embedding + indexing {len(texts)} chunks (batch={_INDEX_BATCH})…")
        for start in tqdm(range(0, len(texts), _INDEX_BATCH), desc="Indexing", unit="batch"):
            end = start + _INDEX_BATCH
            batch_texts = texts[start:end]
            batch_metas = metadatas[start:end]
            batch_ids = ids[start:end]
            try:
                vectors = self.embedder.embed_documents(batch_texts)
                self.store.add(
                    ids=batch_ids,
                    texts=batch_texts,
                    embeddings=vectors,
                    metadatas=batch_metas,
                )
            except Exception as e:  # noqa: BLE001
                log.error(f"Batch [{start}:{end}] failed, skipping: {e}")
                continue

        return {
            "docs": len(docs),
            "chunks": len(chunks),
            "indexed": self.store.count(),
        }

    # ---------- Helpers ----------
    @staticmethod
    def _make_id(meta: dict) -> str:
        src = meta.get("source", "unknown")
        idx = meta.get("chunk_index", 0)
        page = meta.get("page", "")
        # Deterministic ID so re-running upserts instead of duplicating
        base = f"{src}::p{page}::c{idx}"
        return base if len(base) < 200 else f"{Path(str(src)).name}-{uuid.uuid5(uuid.NAMESPACE_URL, base)}"

    @staticmethod
    def _sanitize_meta(meta: dict) -> dict:
        """Chroma only accepts str | int | float | bool in metadata."""
        clean = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                clean[k] = v
            elif v is None:
                continue
            else:
                clean[k] = str(v)
        return clean
