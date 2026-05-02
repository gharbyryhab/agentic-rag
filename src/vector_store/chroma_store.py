"""ChromaDB persistent vector store."""
from __future__ import annotations

from typing import Any

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings

from src.config import get_settings
from src.utils import get_logger
from src.vector_store.base import SearchResult, VectorStore

log = get_logger(__name__)


class ChromaStore(VectorStore):
    """
    Wrapper over a persistent ChromaDB collection.

    We pass embeddings explicitly (computed by BgeEmbedder), so Chroma
    is used purely as a vector index + metadata store.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._cfg = cfg.vector_store

        persist_dir = cfg.absolute_path(self._cfg.persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self._cfg.collection_name,
            metadata={"hnsw:space": self._cfg.distance},
        )
        log.info(
            f"Chroma collection '{self._cfg.collection_name}' "
            f"loaded from {persist_dir} ({self.collection.count()} vectors)"
        )

    # ---------- Write ----------
    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: np.ndarray,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not ids:
            return
        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
        )
        log.debug(f"Upserted {len(ids)} vectors into '{self._cfg.collection_name}'")

    # ---------- Read ----------
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        result = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where,
        )
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0] or [{}] * len(ids)
        # Chroma returns distances (lower = closer for cosine). Convert to similarity.
        dists = result["distances"][0] if result.get("distances") else [0.0] * len(ids)

        return [
            SearchResult(
                id=i,
                text=d,
                score=1.0 - dist,
                metadata=m or {},
            )
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        log.warning(f"Resetting collection '{self._cfg.collection_name}'")
        self.client.delete_collection(self._cfg.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self._cfg.collection_name,
            metadata={"hnsw:space": self._cfg.distance},
        )
