"""Persistent on-disk cache for embeddings : SHA-256(text) -> float32 vector."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.utils.io import ensure_dir, text_hash


class EmbeddingCache:
    """
    Simple file-based cache. One .npy file per text hash.

    Trade-off : many small files, but trivially safe across processes
    and easy to invalidate (just delete the dir). For very large corpora
    consider a single SQLite or LMDB store.
    """

    def __init__(self, cache_dir: str | Path, dim: int) -> None:
        self.cache_dir = ensure_dir(cache_dir)
        self.dim = dim

    # ---------- Single ----------
    def get(self, text: str) -> np.ndarray | None:
        path = self._path_for(text)
        if path.exists():
            return np.load(path)
        return None

    def put(self, text: str, vector: np.ndarray) -> None:
        np.save(self._path_for(text), vector.astype(np.float32))

    # ---------- Batch ----------
    def get_many(
        self, texts: list[str]
    ) -> tuple[list[np.ndarray | None], list[int], list[str]]:
        """
        Returns:
            cached: list of length len(texts), each entry is a vector or None
            missing_idx: indices in `texts` that were cache misses
            missing_texts: corresponding texts
        """
        cached: list[np.ndarray | None] = []
        missing_idx: list[int] = []
        missing_texts: list[str] = []
        for i, t in enumerate(texts):
            vec = self.get(t)
            cached.append(vec)
            if vec is None:
                missing_idx.append(i)
                missing_texts.append(t)
        return cached, missing_idx, missing_texts

    def put_many(self, texts: list[str], vectors: np.ndarray) -> None:
        for t, v in zip(texts, vectors):
            self.put(t, v)

    # ---------- Internals ----------
    def _path_for(self, text: str) -> Path:
        h = text_hash(text)
        # Two-level sharding to avoid huge flat dirs
        sub = self.cache_dir / h[:2]
        sub.mkdir(parents=True, exist_ok=True)
        return sub / f"{h}.npy"
