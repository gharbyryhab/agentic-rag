"""Abstract base class for vector stores."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SearchResult:
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class VectorStore(ABC):
    @abstractmethod
    def add(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: np.ndarray,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None: ...

    @abstractmethod
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def reset(self) -> None: ...
