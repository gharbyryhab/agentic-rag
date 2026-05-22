"""Persistent BM25 lexical index built alongside ChromaDB.

We use `rank-bm25` (BM25Okapi) over a tokenized corpus and persist it via
pickle. For ~135K chunks the in-memory footprint is acceptable (~50-100 MB)
and queries are sub-millisecond.

Storage layout:
    vector_store/bm25/<strategy>/
        corpus.pkl    # list[list[str]]   — tokenized chunks
        ids.pkl       # list[str]         — parallel chunk ids
        texts.pkl     # list[str]         — original chunk texts
        metadatas.pkl # list[dict]        — parallel metadata
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.utils import get_logger
from src.vector_store.base import SearchResult

log = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase + alnum tokens. Good enough for BM25 on technical English."""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class BM25Store:
    """Persistent BM25Okapi index. Append-friendly via full rebuild on save."""

    FILES = ("corpus.pkl", "ids.pkl", "texts.pkl", "metadatas.pkl")

    def __init__(self) -> None:
        cfg = get_settings()
        strategy = cfg.chunking.strategy

        # Strategy-scoped subfolder mirrors the Chroma layout so both indexes
        # always point to the same chunking strategy at the same time.
        self.dir = cfg.absolute_path(cfg.paths.bm25_store) / strategy
        self.dir.mkdir(parents=True, exist_ok=True)

        self._corpus: list[list[str]] = []
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._bm25 = None  # built lazily on first search
        self._load()

    # ---------- Persistence ----------
    def _path(self, name: str) -> Path:
        return self.dir / name

    def _load(self) -> None:
        if not self._path("corpus.pkl").exists():
            log.info(f"BM25 store empty at {self.dir}")
            return
        try:
            with self._path("corpus.pkl").open("rb") as f:
                self._corpus = pickle.load(f)
            with self._path("ids.pkl").open("rb") as f:
                self._ids = pickle.load(f)
            with self._path("texts.pkl").open("rb") as f:
                self._texts = pickle.load(f)
            with self._path("metadatas.pkl").open("rb") as f:
                self._metadatas = pickle.load(f)
            log.info(f"BM25 store loaded ({len(self._ids)} entries)")
        except Exception as e:  # noqa: BLE001
            log.error(f"Failed to load BM25 store: {e}")
            self._corpus, self._ids, self._texts, self._metadatas = [], [], [], []

    def _save(self) -> None:
        with self._path("corpus.pkl").open("wb") as f:
            pickle.dump(self._corpus, f)
        with self._path("ids.pkl").open("wb") as f:
            pickle.dump(self._ids, f)
        with self._path("texts.pkl").open("wb") as f:
            pickle.dump(self._texts, f)
        with self._path("metadatas.pkl").open("wb") as f:
            pickle.dump(self._metadatas, f)

    # ---------- Write ----------
    def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not ids:
            return
        metadatas = metadatas or [{} for _ in ids]
        for id_, text, meta in zip(ids, texts, metadatas):
            self._ids.append(id_)
            self._texts.append(text)
            self._metadatas.append(meta or {})
            self._corpus.append(_tokenize(text))
        self._bm25 = None  # invalidate
        self._save()

    def reset(self) -> None:
        log.warning(f"Resetting BM25 store at {self.dir}")
        self._corpus, self._ids, self._texts, self._metadatas = [], [], [], []
        self._bm25 = None
        for name in self.FILES:
            p = self._path(name)
            if p.exists():
                p.unlink()

    # ---------- Read ----------
    def count(self) -> int:
        return len(self._ids)

    def _ensure_bm25(self):
        if self._bm25 is None and self._corpus:
            try:
                from rank_bm25 import BM25Okapi
            except ImportError as e:
                raise ImportError("Install rank-bm25 via requirements.txt") from e
            self._bm25 = BM25Okapi(self._corpus)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if not self._corpus:
            return []
        self._ensure_bm25()
        if self._bm25 is None:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        # Argpartition for top_k
        import numpy as np
        idx = np.argpartition(-scores, min(top_k, len(scores) - 1))[:top_k]
        idx = idx[np.argsort(-scores[idx])]

        results: list[SearchResult] = []
        for i in idx:
            if scores[i] <= 0:
                continue
            results.append(
                SearchResult(
                    id=self._ids[i],
                    text=self._texts[i],
                    score=float(scores[i]),
                    metadata=self._metadatas[i] or {},
                )
            )
        return results
