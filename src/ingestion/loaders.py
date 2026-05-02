"""Document loaders — uses LangChain community loaders for breadth."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from langchain_community.document_loaders import (
    BSHTMLLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document

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


def load_documents(source: str | Path) -> list[Document]:
    """
    Load all supported documents from a directory or single file.

    Returns LangChain `Document` objects with `page_content` + `metadata`.
    Each document gets a `source` and `file_type` metadata.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    files = list(_iter_files(source))
    log.info(f"Found {len(files)} files to load from {source}")

    docs: list[Document] = []
    for i, path in enumerate(files, 1):
        ext = path.suffix.lower()
        log.info(f"[{i}/{len(files)}] Loading {path.name} ...")
        try:
            loader = _LOADERS[ext](path)
            loaded = loader.load()
            for d in loaded:
                d.metadata.setdefault("source", str(path))
                d.metadata.setdefault("file_type", ext.lstrip("."))
            docs.extend(loaded)
            log.info(f"    -> {len(loaded)} pages (total so far: {len(docs)})")
        except Exception as e:  # noqa: BLE001
            log.error(f"Failed to load {path}: {e}")

    log.info(f"Total documents loaded: {len(docs)} from {source}")
    return docs
