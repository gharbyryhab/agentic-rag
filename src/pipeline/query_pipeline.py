"""End-to-end query : question -> RagAgent -> answer."""
from __future__ import annotations

from concurrent.futures import Future
from typing import Any

from src.agents import ConversationMemory, RagAgent
from src.config import get_settings
from src.embeddings import BgeEmbedder
from src.eval.online_judge import OnlineJudge
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
        cfg = get_settings()
        self.judge = OnlineJudge() if cfg.online_eval.enabled else None
        self._pending_judge: Future | None = None
        log.info("Pipeline prêt.")

    def ask(self, question: str) -> dict[str, Any]:
        result = self.agent.run(question)
        if self.judge:
            self._pending_judge = self.judge.maybe_evaluate(
                question,
                result.get("answer", ""),
                contexts=result.get("contexts", []),
                metadata={"route": result.get("route", "")},
            )
        return result

    def flush_judge(self, timeout: float = 30.0) -> None:
        """Block until the background judge finishes (if one was submitted)."""
        if self._pending_judge is not None:
            try:
                self._pending_judge.result(timeout=timeout)
            except Exception:  # noqa: BLE001
                pass
            self._pending_judge = None

    def reset_history(self) -> None:
        self.memory.clear()
