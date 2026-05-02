"""Abstract LLM interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None, **kwargs: Any) -> str: ...

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...

    @abstractmethod
    def as_langchain(self):
        """Return the underlying LangChain chat model (for use in LangGraph nodes)."""
