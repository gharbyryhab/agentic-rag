"""CrossEncoder-based reranker.

A cross-encoder scores (query, document) pairs jointly. Unlike bi-encoders
(BGE), the query and the document attend to each other through the same
transformer, which gives much better precision at the top of the ranking.

We use `cross-encoder/ms-marco-MiniLM-L-6-v2` by default — 22 M params, fast
on CPU (~10 ms per pair), trained on MS MARCO passage ranking.
"""
from __future__ import annotations

from src.config import get_settings
from src.utils import get_logger
from src.vector_store.base import SearchResult

log = get_logger(__name__)

_singleton: "CrossEncoderReranker | None" = None


class CrossEncoderReranker:
    def __init__(self) -> None:
        cfg = get_settings().retrieval.reranker
        log.info(f"Loading reranker: {cfg.model} on {cfg.device}")
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for the reranker"
            ) from e
        try:
            self._model = CrossEncoder(cfg.model, device=cfg.device, local_files_only=True)
        except (OSError, ValueError) as e:
            raise RuntimeError(
                f"Reranker model '{cfg.model}' not found in local cache. "
                "Run: python -m scripts.download_models"
            ) from e
        self._batch_size = cfg.batch_size

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        if not candidates or top_k <= 0:
            return []
        pairs = [(query, c.text) for c in candidates]
        scores = self._model.predict(pairs, batch_size=self._batch_size, show_progress_bar=False)
        # Build re-ranked list, overwriting score with the cross-encoder score
        ranked = sorted(zip(candidates, scores), key=lambda x: -float(x[1]))
        out: list[SearchResult] = []
        for c, s in ranked[:top_k]:
            out.append(
                SearchResult(
                    id=c.id,
                    text=c.text,
                    score=float(s),
                    metadata=c.metadata,
                    embedding=c.embedding,
                )
            )
        return out


def get_reranker() -> CrossEncoderReranker:
    """Lazily build a process-wide reranker singleton."""
    global _singleton
    if _singleton is None:
        _singleton = CrossEncoderReranker()
    return _singleton
