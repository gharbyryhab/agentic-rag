"""Hybrid + diversified + reranked retriever.

Pipeline :

    query
      │
      ├──► dense (Chroma, with embeddings)   ─┐
      └──► sparse (BM25)                      ├──► RRF fusion
                                              │
                                              ▼
                                      MMR (cosine, diverse)
                                              │
                                              ▼
                                  CrossEncoder rerank
                                              │
                                              ▼
                                          top_k chunks

Each stage is independently toggleable via config/config.yaml.
"""
from __future__ import annotations

from typing import Any

from src.config import get_settings
from src.embeddings import Embedder
from src.retrieval.hybrid import reciprocal_rank_fusion
from src.retrieval.mmr import mmr
from src.retrieval.rerank import get_reranker
from src.utils import get_logger
from src.vector_store import BM25Store, ChromaStore
from src.vector_store.base import SearchResult

log = get_logger(__name__)


class Retriever:
    """Orchestrates dense + sparse retrieval, MMR, and reranking."""

    def __init__(
        self,
        embedder: Embedder,
        store: ChromaStore,
        bm25: BM25Store | None = None,
    ) -> None:
        self.embedder = embedder
        self.store = store
        self.bm25 = bm25
        self._cfg = get_settings().retrieval
        self._reranker = None  # lazy-loaded

    # ---------------- Public API ----------------

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        top_k = top_k or self._cfg.top_k
        fetch_k = self._cfg.fetch_k

        # ---- 1) Dense (Chroma) ----
        q_vec = self.embedder.embed_query(query)
        need_embeddings = self._cfg.mmr.enable
        dense = self.store.search(
            q_vec,
            top_k=fetch_k,
            where=where,
            include_embeddings=need_embeddings,
        )
        log.debug(f"Dense: {len(dense)} candidates")

        # ---- 2) Sparse (BM25) — optional ----
        candidates: list[SearchResult]
        if self._cfg.hybrid.enable and self.bm25 is not None and self.bm25.count() > 0:
            sparse = self.bm25.search(query, top_k=fetch_k)
            log.debug(f"Sparse: {len(sparse)} candidates")
            candidates = reciprocal_rank_fusion(
                [dense, sparse],
                k=self._cfg.hybrid.rrf_k,
                top_k=fetch_k,
            )
            log.debug(f"RRF-fused: {len(candidates)} candidates")
        else:
            candidates = dense

        # Optional score-threshold cut (cosine sim space, ignored if RRF used)
        if self._cfg.score_threshold > 0 and not (
            self._cfg.hybrid.enable and self.bm25 and self.bm25.count() > 0
        ):
            candidates = [c for c in candidates if c.score >= self._cfg.score_threshold]

        # ---- 3) MMR diversification ----
        if self._cfg.mmr.enable and candidates:
            n_after_mmr = min(self._cfg.mmr.candidates_after_mmr, len(candidates))
            candidates = mmr(
                q_vec,
                candidates,
                top_k=n_after_mmr,
                lambda_mult=self._cfg.mmr.lambda_mult,
            )
            log.debug(f"MMR : {len(candidates)} candidates")

        # ---- 4) CrossEncoder rerank ----
        if self._cfg.reranker.enable and candidates:
            if self._reranker is None:
                self._reranker = get_reranker()
            candidates = self._reranker.rerank(query, candidates, top_k=top_k)
            log.debug(f"Reranked : {len(candidates)} final")
        else:
            candidates = candidates[:top_k]

        return candidates
