"""LangGraph-based Agentic RAG.

Graph topology:

    START
      │
      ▼
    rewrite ──(if enabled)──► retrieve ──► grade ──► decide
                                                         │
                              ┌──────────────────────────┤
                              ▼                          ▼
                          generate                   rewrite_again
                              │                          │
                              ▼                          ▼
                             END                     retrieve

Behaviour:
- `rewrite` reformulates the user question using chat history (Multi-Query / HyDE-lite).
- `retrieve` calls the dense retriever (Embedder + ChromaDB).
- `grade` filters out chunks judged irrelevant by Gemini.
- If too few relevant chunks remain, the agent rewrites the query once more (CRAG-style).
- `generate` produces the final answer with citations.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from src.agents.base_agent import BaseAgent
from src.agents.memory import ConversationMemory
from src.config import get_prompts, get_settings
from src.llm import GeminiClient
from src.retrieval import Retriever
from src.utils import get_logger
from src.vector_store.base import SearchResult

log = get_logger(__name__)


# ---------- Graph state ----------
class RagState(TypedDict, total=False):
    question: str
    rewritten_question: str
    documents: list[SearchResult]
    relevant_documents: list[SearchResult]
    answer: str
    iterations: int
    trace: list[dict[str, Any]]


# ---------- Agent ----------
class RagAgent(BaseAgent):
    def __init__(
        self,
        retriever: Retriever,
        llm: GeminiClient,
        memory: ConversationMemory | None = None,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.memory = memory or ConversationMemory()
        self.cfg = get_settings().agent
        self.prompts = get_prompts()
        self.graph = self._build_graph()

    # ---------- Public ----------
    def run(self, question: str, **kwargs: Any) -> dict[str, Any]:
        self.memory.add_user(question)

        initial: RagState = {
            "question": question,
            "rewritten_question": question,
            "iterations": 0,
            "trace": [],
        }
        final: RagState = self.graph.invoke(initial)

        answer = final.get("answer", "")
        self.memory.add_assistant(answer)

        sources = [
            {
                "id": d.id,
                "source": d.metadata.get("source", d.id),
                "score": d.score,
                "snippet": d.text[:200],
            }
            for d in final.get("relevant_documents", [])
        ]
        return {
            "answer": answer,
            "sources": sources,
            "trace": final.get("trace", []),
            "iterations": final.get("iterations", 0),
        }

    # ---------- Graph construction ----------
    def _build_graph(self):
        g = StateGraph(RagState)

        g.add_node("rewrite", self._node_rewrite)
        g.add_node("retrieve", self._node_retrieve)
        g.add_node("grade", self._node_grade)
        g.add_node("generate", self._node_generate)

        if self.cfg.enable_query_rewriting:
            g.add_edge(START, "rewrite")
            g.add_edge("rewrite", "retrieve")
        else:
            g.add_edge(START, "retrieve")

        g.add_edge("retrieve", "grade")
        g.add_conditional_edges(
            "grade",
            self._decide_after_grade,
            {"generate": "generate", "rewrite": "rewrite", "stop": "generate"},
        )
        g.add_edge("generate", END)

        return g.compile()

    # ---------- Nodes ----------
    def _node_rewrite(self, state: RagState) -> RagState:
        # Only reformulate when there's a real conversation context :
        # at least one prior assistant turn. Without that, the query is
        # already standalone and reformulating is a wasted LLM call.
        history_turns = self.memory.history()
        has_prior_assistant = any(t["role"] == "assistant" for t in history_turns)

        if not has_prior_assistant:
            return {
                "rewritten_question": state["question"],
                "trace": state.get("trace", []) + [{"node": "rewrite", "skipped": "first turn"}],
            }

        # Build history without the current user question (last entry)
        prior = history_turns[:-1] if history_turns and history_turns[-1]["role"] == "user" else history_turns
        history_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in prior)

        system = self.prompts["reformulate_system"]
        user = f"Conversation history:\n{history_text}\n\nNew question: {state['question']}"
        try:
            rewritten = self.llm.generate(user, system=system).strip()
        except Exception as e:  # noqa: BLE001
            log.warning(f"Rewrite failed, falling back to original question: {e}")
            rewritten = state["question"]
        log.debug(f"Rewritten: {rewritten}")
        return {
            "rewritten_question": rewritten,
            "trace": state.get("trace", []) + [{"node": "rewrite", "output": rewritten}],
        }

    def _node_retrieve(self, state: RagState) -> RagState:
        q = state.get("rewritten_question") or state["question"]
        docs = self.retriever.retrieve(q)
        log.info(f"Retrieved {len(docs)} candidates for: {q[:80]}")
        return {
            "documents": docs,
            "trace": state.get("trace", []) + [{"node": "retrieve", "n_docs": len(docs)}],
        }

    def _node_grade(self, state: RagState) -> RagState:
        docs = state.get("documents", [])
        if not self.cfg.enable_grading or not docs:
            return {
                "relevant_documents": docs,
                "trace": state.get("trace", []) + [{"node": "grade", "skipped": True}],
            }

        question = state.get("rewritten_question") or state["question"]
        keep: list[SearchResult] = []
        for d in docs:
            verdict = self._grade_one(question, d.text)
            if verdict:
                keep.append(d)

        log.info(f"Graded relevant: {len(keep)}/{len(docs)}")
        return {
            "relevant_documents": keep,
            "trace": state.get("trace", []) + [
                {"node": "grade", "kept": len(keep), "total": len(docs)}
            ],
        }

    def _node_generate(self, state: RagState) -> RagState:
        docs = state.get("relevant_documents") or state.get("documents", [])
        question = state.get("rewritten_question") or state["question"]

        if not docs:
            answer = (
                "I could not find relevant information in the knowledge base "
                "to answer this question reliably."
            )
            return {
                "answer": answer,
                "trace": state.get("trace", []) + [{"node": "generate", "no_context": True}],
            }

        context = "\n\n---\n\n".join(
            f"[source: {d.metadata.get('source', d.id)}]\n{d.text}" for d in docs
        )
        system = self.prompts["rag_system"]
        user = self.prompts["rag_user"].format(context=context, question=question)
        answer = self.llm.generate(user, system=system)
        return {
            "answer": answer,
            "trace": state.get("trace", []) + [{"node": "generate", "answer_len": len(answer)}],
        }

    # ---------- Helpers ----------
    def _grade_one(self, question: str, document: str) -> bool:
        system = self.prompts["grade_system"]
        user = self.prompts["grade_user"].format(document=document[:2000], question=question)
        try:
            verdict = self.llm.generate(user, system=system).strip().lower()
            return verdict.startswith("y")
        except Exception as e:  # noqa: BLE001
            log.warning(f"Grader failed, keeping doc by default: {e}")
            return True

    def _decide_after_grade(self, state: RagState) -> str:
        n_relevant = len(state.get("relevant_documents", []))
        iterations = state.get("iterations", 0)

        if n_relevant >= 1:
            return "generate"
        if iterations < 1:  # one rewrite retry
            state["iterations"] = iterations + 1
            return "rewrite"
        return "stop"
