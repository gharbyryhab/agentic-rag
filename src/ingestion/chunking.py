"""Chunking strategies : semantic (default) or recursive.

Semantic chunking uses sentence embeddings (BGE) to detect topic boundaries.
A post-processing pass enforces min/max chunk sizes by re-splitting oversized
chunks with a recursive splitter and dropping (or merging) undersized ones.
"""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.ingestion.cleaners import clean_text
from src.utils import get_logger

log = get_logger(__name__)


# ---------- Builders ----------

def _build_recursive_splitter() -> RecursiveCharacterTextSplitter:
    cfg = get_settings().chunking
    return RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separators=cfg.separators,
        length_function=len,
    )


def _build_semantic_splitter():
    """Lazy import to avoid loading langchain_experimental when not needed."""
    cfg = get_settings()
    try:
        from langchain_experimental.text_splitter import SemanticChunker
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as e:
        raise ImportError(
            "Semantic chunking requires `langchain-experimental` and "
            "`langchain-huggingface`. Install via requirements.txt."
        ) from e

    log.info(
        f"Building SemanticChunker (model={cfg.embeddings.model_name}, "
        f"breakpoint={cfg.chunking.semantic_breakpoint_type}={cfg.chunking.semantic_breakpoint_amount})"
    )
    embedder = HuggingFaceEmbeddings(
        model_name=cfg.embeddings.model_name,
        model_kwargs={"device": cfg.embeddings.device},
        encode_kwargs={"normalize_embeddings": cfg.embeddings.normalize},
    )
    return SemanticChunker(
        embedder,
        breakpoint_threshold_type=cfg.chunking.semantic_breakpoint_type,
        breakpoint_threshold_amount=cfg.chunking.semantic_breakpoint_amount,
        buffer_size=cfg.chunking.semantic_buffer_size,
    )


# ---------- Post-processing : enforce min/max sizes ----------

def _enforce_size_bounds(chunks: list[Document]) -> list[Document]:
    """
    - Re-split chunks > max_chunk_chars using RecursiveCharacterTextSplitter
    - Merge consecutive chunks (same source) when one is < min_chunk_chars
    """
    cfg = get_settings().chunking
    splitter = _build_recursive_splitter()

    # Step 1 : re-split oversized
    expanded: list[Document] = []
    for c in chunks:
        if len(c.page_content) > cfg.max_chunk_chars:
            sub = splitter.split_documents([c])
            expanded.extend(sub)
        else:
            expanded.append(c)

    # Step 2 : merge undersized with neighbour from same book
    merged: list[Document] = []
    buffer: Document | None = None
    for c in expanded:
        if buffer is None:
            buffer = c
            continue
        same_book = buffer.metadata.get("source") == c.metadata.get("source")
        if (
            same_book
            and len(buffer.page_content) < cfg.min_chunk_chars
            and len(buffer.page_content) + len(c.page_content) <= cfg.max_chunk_chars
        ):
            buffer.page_content = (buffer.page_content + "\n\n" + c.page_content).strip()
            # keep buffer.metadata (parent), do not overwrite
        else:
            merged.append(buffer)
            buffer = c
    if buffer is not None:
        merged.append(buffer)

    return merged


# ---------- Public API ----------

def chunk_documents(documents: list[Document], clean: bool = True) -> list[Document]:
    """
    Split documents into chunks using the strategy from config.yaml.

    `chunking.strategy: semantic` → SemanticChunker (BGE-based)
    `chunking.strategy: recursive` → RecursiveCharacterTextSplitter

    Each chunk inherits parent metadata + receives a `chunk_index`.
    Post-processing enforces min/max size bounds.
    """
    cfg = get_settings().chunking

    if clean:
        for d in documents:
            d.page_content = clean_text(d.page_content)

    strategy = (cfg.strategy or "recursive").lower()
    log.info(f"Chunking strategy: {strategy}")

    if strategy == "semantic":
        splitter = _build_semantic_splitter()
        # SemanticChunker only exposes split_text / create_documents,
        # so we need to call it per document to preserve metadata.
        chunks: list[Document] = []
        for d in documents:
            text = d.page_content
            if not text.strip():
                continue
            try:
                sub_texts = splitter.split_text(text)
            except Exception as e:  # noqa: BLE001
                log.warning(f"SemanticChunker failed on a doc, falling back to recursive: {e}")
                sub_texts = _build_recursive_splitter().split_text(text)
            for st in sub_texts:
                chunks.append(Document(page_content=st, metadata=dict(d.metadata)))
    else:
        chunks = _build_recursive_splitter().split_documents(documents)

    # Post-process : enforce size bounds
    chunks = _enforce_size_bounds(chunks)

    # Annotate chunk_index per source
    counter: dict[str, int] = {}
    for c in chunks:
        src = c.metadata.get("source", "unknown")
        idx = counter.get(src, 0)
        c.metadata["chunk_index"] = idx
        counter[src] = idx + 1

    log.info(f"Chunked {len(documents)} docs into {len(chunks)} chunks (after post-processing)")
    return chunks
