"""Document loaders — uses LangChain community loaders for breadth.

Enriches each Document with Tier-1 metadata (book_id, book_title, author,
category, domain, level, language, is_practical/theoretical/pedagogical, page)
sourced from the classifier output `results/metadata/books_metadata.json`.

Also strips repeating headers/footers per book (detected by frequency).
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Iterator

from langchain_community.document_loaders import (
    BSHTMLLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document

from src.config import get_settings
from src.ingestion.book_metadata import get_book_metadata_store
from src.utils import get_logger

log = get_logger(__name__)

# Silence pypdf's noisy "Could not reliably determine page label" warnings
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)
logging.getLogger("pypdf.generic").setLevel(logging.ERROR)


# Map file extensions to a loader factory
_LOADERS = {
    ".pdf": lambda p: PyPDFLoader(str(p)),
    ".md": lambda p: UnstructuredMarkdownLoader(str(p)),
    ".markdown": lambda p: UnstructuredMarkdownLoader(str(p)),
    ".html": lambda p: BSHTMLLoader(str(p)),
    ".htm": lambda p: BSHTMLLoader(str(p)),
    ".txt": lambda p: TextLoader(str(p), encoding="utf-8"),
}


def _iter_files(source: Path) -> Iterator[Path]:
    if source.is_file():
        yield source
        return
    for path in source.rglob("*"):
        if path.is_file() and path.suffix.lower() in _LOADERS:
            yield path


# ----- Header / footer detection -----------------------------------------------------------

def _strip_repeating_headers_footers(pages: list[Document]) -> int:
    """
    Detect lines that appear on >= occurrence_ratio of pages of the same book
    among the first/last N lines, and remove them in-place.

    Returns the number of distinct lines stripped.
    """
    cfg = get_settings().header_footer
    if not cfg.enable or len(pages) < 5:
        return 0

    n_first = cfg.scan_first_lines
    n_last = cfg.scan_last_lines
    threshold = max(2, int(len(pages) * cfg.occurrence_ratio))

    counter: Counter[str] = Counter()
    for d in pages:
        lines = [ln.strip() for ln in d.page_content.splitlines() if ln.strip()]
        if not lines:
            continue
        # First and last N lines (likely header / footer zones)
        for ln in lines[:n_first] + lines[-n_last:]:
            # Ignore very short / very long lines (less likely to be headers)
            if 3 <= len(ln) <= 120:
                counter[ln] += 1

    repeating = {ln for ln, n in counter.items() if n >= threshold}
    if not repeating:
        return 0

    for d in pages:
        new_lines = []
        for ln in d.page_content.splitlines():
            if ln.strip() in repeating:
                continue
            new_lines.append(ln)
        d.page_content = "\n".join(new_lines)

    return len(repeating)


# ----- Main -----------------------------------------------------------------------------

def load_documents(source: str | Path) -> list[Document]:
    """
    Load all supported documents from a directory or single file.

    Each Document carries Tier-1 metadata sourced from the book classifier
    (when available) plus per-page `page` and the `source` path.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    book_meta = get_book_metadata_store()
    files = list(_iter_files(source))
    log.info(f"Found {len(files)} files to load from {source}")
    log.info(f"Book metadata store size: {len(book_meta)} entries")

    docs: list[Document] = []
    for i, path in enumerate(files, 1):
        ext = path.suffix.lower()
        log.info(f"[{i}/{len(files)}] Loading {path.name} ...")
        try:
            loader = _LOADERS[ext](path)
            loaded = loader.load()
        except Exception as e:  # noqa: BLE001
            log.error(f"Failed to load {path}: {e}")
            continue

        if not loaded:
            log.warning(f"    -> no pages extracted from {path.name}")
            continue

        # Header/footer cleanup BEFORE chunking
        n_stripped = _strip_repeating_headers_footers(loaded)
        if n_stripped:
            log.debug(f"    stripped {n_stripped} repeating header/footer lines")

        # Inject Tier-1 metadata on every page
        chroma_meta = book_meta.chroma_metadata(path)
        for d in loaded:
            d.metadata["source"] = str(path)
            d.metadata["file_type"] = ext.lstrip(".")
            for k, v in chroma_meta.items():
                d.metadata[k] = v
            # `page` is normally injected by PyPDFLoader; ensure int / fallback to 0
            if "page" in d.metadata and not isinstance(d.metadata["page"], int):
                try:
                    d.metadata["page"] = int(d.metadata["page"])
                except (ValueError, TypeError):
                    d.metadata["page"] = 0
            elif "page" not in d.metadata:
                d.metadata["page"] = 0

        docs.extend(loaded)
        log.info(f"    -> {len(loaded)} pages (total so far: {len(docs)})")

    log.info(f"Total documents loaded: {len(docs)} from {source}")
    return docs
