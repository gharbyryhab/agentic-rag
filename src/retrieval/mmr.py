"""Cosine-based Maximal Marginal Relevance.

Picks documents that are both relevant to the query AND diverse from
already-selected ones. Requires each candidate to carry its embedding.
"""
from __future__ import annotations

import numpy as np

from src.vector_store.base import SearchResult


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def mmr(
    query_embedding: np.ndarray,
    candidates: list[SearchResult],
    top_k: int,
    lambda_mult: float = 0.6,
) -> list[SearchResult]:
    """
    Greedy MMR :  score(d) = λ * sim(q, d) − (1 − λ) * max sim(d, s) for s in selected.

    Candidates without embeddings fall back to their original score for relevance
    and contribute no diversity penalty (effectively pure relevance ranking).
    """
    if not candidates or top_k <= 0:
        return []

    remaining = list(candidates)
    selected: list[SearchResult] = []

    # Precompute relevance scores
    relevance = {}
    for c in remaining:
        if c.embedding is not None:
            relevance[c.id] = _cosine(query_embedding, c.embedding)
        else:
            relevance[c.id] = c.score

    while remaining and len(selected) < top_k:
        if not selected:
            # First pick : maximize relevance
            best = max(remaining, key=lambda c: relevance[c.id])
            selected.append(best)
            remaining.remove(best)
            continue

        best_score = -1e9
        best_idx = 0
        for i, cand in enumerate(remaining):
            rel = relevance[cand.id]
            if cand.embedding is None:
                diversity_penalty = 0.0
            else:
                diversity_penalty = max(
                    (
                        _cosine(cand.embedding, s.embedding)
                        if s.embedding is not None
                        else 0.0
                    )
                    for s in selected
                )
            score = lambda_mult * rel - (1.0 - lambda_mult) * diversity_penalty
            if score > best_score:
                best_score = score
                best_idx = i

        selected.append(remaining.pop(best_idx))

    return selected
