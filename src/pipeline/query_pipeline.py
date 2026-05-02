"""End-to-end query : question -> RagAgent -> answer."""
from __future__ import annotations

from typing import Any

from src.agents import ConversationMemory, RagAgent
from src.embeddings import BgeEmbedder
from src.llm import GeminiClient
from src.retrieval import Retriever
from src.utils import get_logger
from src.vector_store import ChromaStore

log = get_logger(__name__)


class QueryPipeline:
    """Convenience wrapper that wires the full agentic stack together."""

    def __init__(self) -> None:
        log.info("Initializing query pipeline…")
        self.embedder = BgeEmbedder()
        self.store = ChromaStore()
        self.retriever = Retriever(self.embedder, self.store)
        self.llm = GeminiClient()
        self.memory = ConversationMemory(max_turns=10)
        self.agent = RagAgent(self.retriever, self.llm, memory=self.memory)
        log.info("Query pipeline ready.")

    def ask(self, question: str) -> dict[str, Any]:
        return self.agent.run(question)

    def reset_history(self) -> None:
        self.memory.clear()
