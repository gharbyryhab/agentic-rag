"""Chunking strategies."""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.ingestion.cleaners import clean_text
from src.utils import get_logger

log = get_logger(__name__)


def _build_splitter() -> RecursiveCharacterTextSplitter:
    cfg = get_settings().chunking
    return RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=cfg.separators,
        length_function=len,
    )


def chunk_documents(documents: list[Document], clean: bool = True) -> list[Document]:
    """
    Split documents into chunks using the strategy from config.yaml.

    Each chunk inherits parent metadata + receives a `chunk_index`.
    """
    splitter = _build_splitter()

    if clean:
        for d in documents:
            d.page_content = clean_text(d.page_content)

    chunks = splitter.split_documents(documents)

    # Annotate chunks
    counter: dict[str, int] = {}
    for c in chunks:
        src = c.metadata.get("source", "unknown")
        idx = counter.get(src, 0)
        c.metadata["chunk_index"] = idx
        counter[src] = idx + 1

    log.info(f"Chunked {len(documents)} docs into {len(chunks)} chunks")
    return chunks
