"""Hybrid retrieval : fuses dense (Chroma) and sparse (BM25) rankings via RRF.

Reciprocal Rank Fusion (Cormack et al. 2009) is parameter-light, robust to
scale differences between scoring systems, and used by Vespa / Elasticsearch.

    RRF_score(d) = Σ_i  1 / (k + rank_i(d))

where rank_i(d) is the 1-indexed rank of document d in retriever i.
"""
from __future__ import annotations

from src.vector_store.base import SearchResult


def reciprocal_rank_fusion(
    rankings: list[list[SearchResult]],
    k: int = 60,
    top_k: int = 30,
) -> list[SearchResult]:
    """
    Args:
        rankings: list of ranked SearchResult lists (one per retriever).
        k: RRF constant. 60 is the canonical default.
        top_k: max output length.

    Returns:
        Fused list, sorted by descending RRF score. The first occurrence of
        each document wins for `text`/`embedding` (typically from the dense
        retriever which carries the embedding).
    """
    rrf_scores: dict[str, float] = {}
    docs: dict[str, SearchResult] = {}

    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            rrf_scores[doc.id] = rrf_scores.get(doc.id, 0.0) + 1.0 / (k + rank)
            # Keep the first occurrence (preserves embedding if dense ranking comes first)
            if doc.id not in docs:
                docs[doc.id] = doc
            elif docs[doc.id].embedding is None and doc.embedding is not None:
                docs[doc.id] = doc

    ranked_ids = sorted(rrf_scores.items(), key=lambda x: -x[1])[:top_k]
    fused: list[SearchResult] = []
    for doc_id, fused_score in ranked_ids:
        d = docs[doc_id]
        # Replace transport score with RRF score so downstream sees fused ranking
        fused.append(
            SearchResult(
                id=d.id,
                text=d.text,
                score=fused_score,
                metadata=d.metadata,
                embedding=d.embedding,
            )
        )
    return fused
