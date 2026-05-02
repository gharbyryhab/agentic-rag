"""Abstract base class for embedders."""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Embedder(ABC):
    """Interface for any embedding model. Swap implementations freely."""

    dimension: int

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """Embed a list of passages. Returns array of shape (n, dim)."""

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray:
        """Embed a single user query. Returns array of shape (dim,)."""
