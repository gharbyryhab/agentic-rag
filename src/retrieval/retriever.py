"""Dense retriever combining an Embedder + a VectorStore, with optional MMR."""
from __future__ import annotations

from typing import Any

import numpy as np

from src.config import get_settings
from src.embeddings import Embedder
from src.utils import get_logger
from src.vector_store import VectorStore
from src.vector_store.base import SearchResult

log = get_logger(__name__)


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore) -> None:
        self.embedder = embedder
        self.store = store
        self._cfg = get_settings().retrieval

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        top_k = top_k or self._cfg.top_k
        q_vec = self.embedder.embed_query(query)

        if not self._cfg.use_mmr:
            return self.store.search(q_vec, top_k=top_k, where=where)

        # MMR : fetch more candidates, then rerank for diversity
        candidates = self.store.search(q_vec, top_k=self._cfg.fetch_k, where=where)
        return self._mmr(q_vec, candidates, top_k, self._cfg.mmr_lambda)

    # ---------- MMR ----------
    @staticmethod
    def _mmr(
        query_vec: np.ndarray,
        candidates: list[SearchResult],
        top_k: int,
        lambda_mult: float,
    ) -> list[SearchResult]:
        """
        Maximal Marginal Relevance — picks results that are both relevant
        to the query AND diverse from already-picked results.
        """
        if not candidates:
            return []

        # Approximate candidate vectors from their similarity scores ; here
        # we don't have raw vectors back from Chroma, so we re-rank using
        # text-overlap as a cheap diversity proxy.
        # NOTE : for true MMR, store vectors alongside results — left as TODO.
        selected: list[SearchResult] = []
        remaining = list(candidates)

        while remaining and len(selected) < top_k:
            if not selected:
                selected.append(remaining.pop(0))
                continue

            best_idx, best_score = 0, -1e9
            for i, cand in enumerate(remaining):
                relevance = cand.score
                diversity_penalty = max(
                    _token_overlap(cand.text, s.text) for s in selected
                )
                score = lambda_mult * relevance - (1 - lambda_mult) * diversity_penalty
                if score > best_score:
                    best_score, best_idx = score, i
            selected.append(remaining.pop(best_idx))

        return selected


def _token_overlap(a: str, b: str) -> float:
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
