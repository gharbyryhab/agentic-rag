"""End-to-end query : question -> RagAgent -> answer."""
from __future__ import annotations

from typing import Any

from src.agents import ConversationMemory, RagAgent
from src.embeddings import BgeEmbedder
from src.llm import GeminiClient
from src.retrieval import Retriever
from src.utils import get_logger
from src.vector_store import BM25Store, ChromaStore

log = get_logger(__name__)


class QueryPipeline:
    """Wires the full agentic stack together (Phase II + III)."""

    def __init__(self) -> None:
        log.info("Chargement du pipeline (première fois ~10s, modèles BGE + reranker)…")
        self.embedder = BgeEmbedder()
        self.store = ChromaStore()
        self.bm25 = BM25Store()
        self.retriever = Retriever(self.embedder, self.store, bm25=self.bm25)
        self.llm = GeminiClient()
        self.memory = ConversationMemory(max_turns=10)
        self.agent = RagAgent(
            retriever=self.retriever,
            llm=self.llm,
            memory=self.memory,
        )
        log.info("Pipeline prêt.")

    def ask(self, question: str) -> dict[str, Any]:
        return self.agent.run(question)

    def reset_history(self) -> None:
        self.memory.clear()
