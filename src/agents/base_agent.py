"""Abstract base for agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    @abstractmethod
    def run(self, question: str, **kwargs: Any) -> dict[str, Any]:
        """Process a single user question and return a dict with at least:
        - answer: str
        - sources: list[dict]
        - trace: list[dict]   # the steps taken
        """
