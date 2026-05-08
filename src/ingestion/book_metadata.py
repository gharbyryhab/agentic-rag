"""Lookup table for per-book metadata produced by maintenance/classify_books.py.

Two-tier metadata strategy:
  - Tier 1 (Chroma) : light scalar fields injected on every chunk for filtering
                      (book_id, book_title, author, category, domain, level,
                       language, is_practical, is_theoretical, is_pedagogical, page)
  - Tier 2 (JSON)   : rich fields (description, key_chapters, target_audience,
                      sub_domains) accessed on demand from this store, NOT
                      pushed to Chroma to keep metadata light.

The classifier output lives at `results/metadata/books_metadata.json` and is
keyed by the PDF filename (basename, case-sensitive). Each entry has fields:
    title, author, main_domain, detected_domain, sub_domains, level,
    target_audience, language, pedagogical, practical, theoretical,
    key_chapters, description, folder, extraction_method, toc_extracted
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.utils import get_logger

log = get_logger(__name__)


def _slugify(text: str) -> str:
    """Convert a book title into a stable identifier."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:80]


class BookMetadataStore:
    """Loads and queries book-level metadata produced by the classifier."""

    def __init__(self, path: str | Path | None = None) -> None:
        cfg = get_settings()
        self.path = Path(path) if path else cfg.absolute_path(cfg.paths.books_metadata)
        self._by_filename: dict[str, dict[str, Any]] = {}
        self._by_book_id: dict[str, dict[str, Any]] = {}
        self._load()

    # ---------- Loading ----------
    def _load(self) -> None:
        if not self.path.exists():
            log.warning(
                f"Books metadata file not found at {self.path}. "
                f"Chunks will be indexed without rich metadata. "
                f"Run `python -m maintenance.classify_books` to generate it."
            )
            return

        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:  # noqa: BLE001
            log.error(f"Failed to read {self.path}: {e}")
            return

        if not isinstance(raw, dict):
            log.error(f"Expected dict in {self.path}, got {type(raw).__name__}")
            return

        skipped = 0
        for filename, meta in raw.items():
            if not isinstance(meta, dict):
                skipped += 1
                continue
            if "error" in meta:
                # Classifier failed on this book — keep but mark
                log.debug(f"Skipping classification error for {filename}: {meta.get('error')}")
                skipped += 1
                continue

            # Build a stable book_id from title (fallback to filename)
            title = meta.get("title") or Path(filename).stem
            book_id = _slugify(title)
            meta = {**meta, "book_id": book_id}

            self._by_filename[filename] = meta
            self._by_book_id[book_id] = meta

        log.info(
            f"Loaded {len(self._by_filename)} book entries from {self.path.name} "
            f"(skipped: {skipped})"
        )

    # ---------- Public API ----------
    def get_by_path(self, pdf_path: str | Path) -> dict[str, Any] | None:
        """Lookup by the source file path. Falls back to basename match."""
        filename = Path(pdf_path).name
        return self._by_filename.get(filename)

    def get_by_id(self, book_id: str) -> dict[str, Any] | None:
        return self._by_book_id.get(book_id)

    def chroma_metadata(self, pdf_path: str | Path) -> dict[str, Any]:
        """
        Build the Tier 1 (Chroma) metadata dict for a given PDF.
        Returns scalars only — list/dict fields are kept in Tier 2 (this store).
        """
        path = Path(pdf_path)
        meta = self.get_by_path(path)

        # Defaults extracted from filename / folder when classifier failed
        category = path.parent.name
        fallback = {
            "category": category,
            "book_title": path.stem[:200],
            "author": "",
            "domain": "miscellaneous",
            "domain_label": category,
            "level": "intermediate",
            "language": "en",
            "is_pedagogical": False,
            "is_practical": False,
            "is_theoretical": False,
            "book_id": _slugify(path.stem),
        }

        if not meta:
            return fallback

        return {
            "category": meta.get("folder") or category,
            "book_title": meta.get("title") or path.stem,
            "author": meta.get("author") or "",
            "domain": meta.get("main_domain") or "miscellaneous",
            "domain_label": meta.get("detected_domain") or category,
            "level": meta.get("level") or "intermediate",
            "language": meta.get("language") or "en",
            "is_pedagogical": bool(meta.get("pedagogical", False)),
            "is_practical": bool(meta.get("practical", False)),
            "is_theoretical": bool(meta.get("theoretical", False)),
            "book_id": meta.get("book_id"),
        }

    def __len__(self) -> int:
        return len(self._by_filename)


@lru_cache(maxsize=1)
def get_book_metadata_store() -> BookMetadataStore:
    """Singleton accessor."""
    return BookMetadataStore()
