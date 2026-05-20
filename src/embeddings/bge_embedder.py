"""BAAI/bge-small-en-v1.5 wrapper using sentence-transformers."""
from __future__ import annotations

import os
import sys
import warnings

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import get_settings
from src.embeddings.base import Embedder
from src.embeddings.cache import EmbeddingCache
from src.utils import get_logger

warnings.filterwarnings("ignore", category=FutureWarning)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

log = get_logger(__name__)


def _patch_windows_getaddrinfo() -> None:
    """Redirect socket.getaddrinfo through a fresh thread on Windows.

    Loading safetensors model weights corrupts the main thread's Windows
    Thread-Local Storage (TLS) slot used by the DNS resolver
    (ws2_32!getaddrinfo → dnsapi!DnsQuery_W).  New threads start with clean
    TLS, so delegating DNS lookups there avoids the access-violation crash
    that would otherwise kill the process silently (exit code 5).

    Guard: no-op on non-Windows and idempotent (safe to call multiple times).
    """
    if sys.platform != "win32":
        return
    import socket
    import threading

    if getattr(socket.getaddrinfo, "_tls_patched", False):
        return  # already patched

    _orig = socket.getaddrinfo

    def _safe_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        _result: list = [None]
        _error: list = [None]

        def _run() -> None:
            try:
                _result[0] = _orig(host, port, family, type, proto, flags)
            except Exception as exc:  # noqa: BLE001
                _error[0] = exc

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=30)
        if _error[0] is not None:
            raise _error[0]
        if _result[0] is None:
            raise OSError(f"getaddrinfo timed out for {host!r}")
        return _result[0]

    _safe_getaddrinfo._tls_patched = True  # type: ignore[attr-defined]
    socket.getaddrinfo = _safe_getaddrinfo
    log.debug("Windows socket.getaddrinfo patched to use fresh-thread DNS (TLS fix)")


class BgeEmbedder(Embedder):
    """
    BGE small (33 M params, 384-D vectors).

    Designed for CPU inference on modest hardware (i3 + 12 GB RAM).
    Adds the BAAI-recommended query prefix and supports a disk cache to
    avoid re-embedding unchanged chunks across runs.
    """

    def __init__(self, use_cache: bool = True) -> None:
        cfg = get_settings()
        self._cfg = cfg.embeddings

        log.info(f"Loading embedding model: {self._cfg.model_name} on {self._cfg.device}")
        try:
            self.model = SentenceTransformer(
                self._cfg.model_name,
                device=self._cfg.device,
                local_files_only=True,
            )
        except (OSError, ValueError) as e:
            raise RuntimeError(
                f"Embedding model '{self._cfg.model_name}' not found in local cache. "
                "Run: python -m scripts.download_models"
            ) from e
        self.dimension = self.model.get_embedding_dimension()

        # Safetensors corrupts the main-thread Windows DNS TLS slot — patch now
        # so subsequent HTTP calls (Gemini API, web search) work correctly.
        _patch_windows_getaddrinfo()

        self.cache: EmbeddingCache | None = None
        if use_cache:
            cache_dir = cfg.absolute_path(cfg.paths.embedding_cache)
            self.cache = EmbeddingCache(cache_dir, dim=self.dimension)
            log.info(f"Embedding cache enabled at {cache_dir}")

    # ---------- Public API ----------
    def embed_documents(self, texts: list[str]) -> np.ndarray:
        prefix = self._cfg.passage_prefix
        prefixed = [prefix + t for t in texts] if prefix else list(texts)
        return self._embed(prefixed, use_cache=True)

    def embed_query(self, text: str) -> np.ndarray:
        prefixed = self._cfg.query_prefix + text if self._cfg.query_prefix else text
        return self._embed([prefixed], use_cache=False)[0]

    # ---------- Internals ----------
    def _embed(self, texts: list[str], use_cache: bool) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        if self.cache is None or not use_cache:
            return self._encode(texts)

        # Cache lookup
        cached, missing_idx, missing_texts = self.cache.get_many(texts)
        if missing_texts:
            log.debug(f"Cache miss for {len(missing_texts)}/{len(texts)} texts")
            new_vecs = self._encode(missing_texts)
            self.cache.put_many(missing_texts, new_vecs)
            for idx, vec in zip(missing_idx, new_vecs):
                cached[idx] = vec
        return np.stack(cached, axis=0)

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            batch_size=self._cfg.batch_size,
            normalize_embeddings=self._cfg.normalize,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 64,
        )
        return vectors.astype(np.float32)
