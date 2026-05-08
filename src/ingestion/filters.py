"""Chunk filtering and near-duplicate detection."""
from __future__ import annotations

from typing import Iterable

from langchain_core.documents import Document

from src.config import get_settings
from src.utils import get_logger

log = get_logger(__name__)


# ---------- Pathological chunks --------------------------------------------------

def is_pathological(text: str, min_chars: int, max_chars: int,
                    min_alpha_ratio: float, min_vocab_diversity: float) -> tuple[bool, str]:
    """Return (True, reason) if the chunk should be discarded."""
    if not text:
        return True, "empty"

    n = len(text)
    if n < min_chars:
        return True, "too_short"
    if n > max_chars:
        return True, "too_long"

    alpha = sum(c.isalpha() for c in text)
    if alpha / n < min_alpha_ratio:
        return True, "low_alpha_ratio"

    words = text.split()
    if len(words) < 5:
        return True, "too_few_words"
    diversity = len(set(words)) / len(words)
    if diversity < min_vocab_diversity:
        return True, "low_vocab_diversity"

    return False, "ok"


def filter_pathological(chunks: list[Document]) -> list[Document]:
    cfg = get_settings()
    if not cfg.filters.enable_pathological_filter:
        return chunks

    fcfg = cfg.filters
    ccfg = cfg.chunking

    kept: list[Document] = []
    reasons: dict[str, int] = {}
    for c in chunks:
        bad, reason = is_pathological(
            c.page_content,
            min_chars=ccfg.min_chunk_chars,
            max_chars=ccfg.max_chunk_chars,
            min_alpha_ratio=fcfg.min_alpha_ratio,
            min_vocab_diversity=fcfg.min_vocab_diversity,
        )
        if bad:
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            kept.append(c)

    log.info(
        f"Pathological filter: kept {len(kept)}/{len(chunks)} "
        f"(removed by reason: {reasons})"
    )
    return kept


# ---------- Near-duplicate detection (MinHash-LSH) -------------------------------

def _shingles(text: str, k: int = 5) -> set[str]:
    """k-shingles of words for MinHash."""
    words = text.lower().split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def deduplicate(chunks: list[Document]) -> list[Document]:
    """
    Detect near-duplicate chunks via MinHash-LSH and keep the first occurrence.

    Two chunks with Jaccard similarity ≥ threshold on 5-word shingles are
    considered duplicates.
    """
    cfg = get_settings().filters
    if not cfg.enable_dedup or len(chunks) < 2:
        return chunks

    try:
        from datasketch import MinHash, MinHashLSH
    except ImportError:
        log.error("datasketch not installed. Skipping dedup. Run: pip install datasketch")
        return chunks

    lsh = MinHashLSH(
        threshold=cfg.dedup_jaccard_threshold,
        num_perm=cfg.dedup_num_perm,
    )
    minhashes: dict[int, MinHash] = {}

    kept: list[Document] = []
    duplicates_count = 0

    for i, c in enumerate(chunks):
        shingles = _shingles(c.page_content)
        if not shingles:
            continue

        m = MinHash(num_perm=cfg.dedup_num_perm)
        for s in shingles:
            m.update(s.encode("utf-8"))

        # Query first — if a near-duplicate already exists, skip
        if lsh.query(m):
            duplicates_count += 1
            continue

        lsh.insert(str(i), m)
        minhashes[i] = m
        kept.append(c)

    log.info(
        f"Deduplication: kept {len(kept)}/{len(chunks)} "
        f"(removed {duplicates_count} near-duplicates, "
        f"threshold={cfg.dedup_jaccard_threshold})"
    )
    return kept


# ---------- Combined pipeline ----------------------------------------------------

def apply_filters(chunks: list[Document]) -> list[Document]:
    """Apply pathological filter then deduplication, in this order."""
    chunks = filter_pathological(chunks)
    chunks = deduplicate(chunks)
    return chunks
