"""Unified Agentic RAG : Router → (CRAG-light | ReAct).

Graph for the SIMPLE path (default, fast) :

    START
      │
      ▼
    rewrite ──► retrieve ──► grade ──► generate ──► END

Graph for the AGENT path (multi-step, tool-using) :

    START ──► react_agent ──► END

The top-level `RagAgent.run()` invokes the router, then dispatches to one
of the two sub-pipelines. Conversation memory is shared.
"""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.base_agent import BaseAgent
from src.agents.memory import ConversationMemory
from src.agents.react_agent import ReActAgent
from src.agents.router import QueryRouter
from src.config import get_prompts, get_settings
from src.llm import GeminiClient
from src.retrieval import Retriever
from src.utils import get_logger
from src.vector_store.base import SearchResult

log = get_logger(__name__)


# ------------ State for the CRAG-light sub-graph ------------

class RagState(TypedDict, total=False):
    question: str
    rewritten_question: str
    documents: list[SearchResult]
    relevant_documents: list[SearchResult]
    answer: str
    iterations: int
    trace: list[dict[str, Any]]


# ------------ Main agent ------------

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

        # Components
        self.router = QueryRouter(llm)
        self.simple_graph = self._build_simple_graph()
        self.react_agent = ReActAgent(retriever, llm)

    # ---------- Public ----------

    def run(self, question: str, **kwargs: Any) -> dict[str, Any]:
        self.memory.add_user(question)

        # 1) Route
        route = self.router.route(question)
        log.info(f"Routing → {route}")

        # 2) Dispatch
        if route == "agent":
            result = self.react_agent.run(question)
            result["route"] = "agent"
        else:
            result = self._run_simple(question)
            result["route"] = "simple"

        self.memory.add_assistant(result.get("answer", ""))
        return result

    # ---------- Simple (CRAG-light) ----------

    def _run_simple(self, question: str) -> dict[str, Any]:
        initial: RagState = {
            "question": question,
            "rewritten_question": question,
            "iterations": 0,
            "trace": [],
        }
        final: RagState = self.simple_graph.invoke(initial)

        sources = [
            {
                "id": d.id,
                "source": d.metadata.get("source", d.id),
                "book_title": d.metadata.get("book_title", ""),
                "page": d.metadata.get("page", ""),
                "score": d.score,
                "snippet": d.text[:300],
            }
            for d in final.get("relevant_documents", [])
        ]
        return {
            "answer": final.get("answer", ""),
            "sources": sources,
            "trace": final.get("trace", []),
            "iterations": final.get("iterations", 0),
        }

    # ---------- Graph construction (CRAG-light) ----------

    def _build_simple_graph(self):
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
        history = self.memory.history()
        has_prior_assistant = any(t["role"] == "assistant" for t in history)
        if not has_prior_assistant:
            return {
                "rewritten_question": state["question"],
                "trace": state.get("trace", []) + [{"node": "rewrite", "skipped": "first turn"}],
            }

        prior = history[:-1] if history and history[-1]["role"] == "user" else history
        history_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in prior)

        system = self.prompts["reformulate_system"]
        user = f"Conversation history:\n{history_text}\n\nNew question: {state['question']}"
        try:
            rewritten = self.llm.generate(user, system=system).strip()
        except Exception as e:  # noqa: BLE001
            log.warning(f"Rewrite failed: {e}")
            rewritten = state["question"]
        return {
            "rewritten_question": rewritten,
            "trace": state.get("trace", []) + [{"node": "rewrite", "output": rewritten[:120]}],
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
            if self._grade_one(question, d.text):
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
            return {
                "answer": "I could not find relevant information in the knowledge base.",
                "trace": state.get("trace", []) + [{"node": "generate", "no_context": True}],
            }
        context = "\n\n---\n\n".join(
            f"[{d.metadata.get('book_title') or d.metadata.get('source', d.id)}"
            + (f", p.{d.metadata.get('page')}" if d.metadata.get('page') else "")
            + f"]\n{d.text}"
            for d in docs
        )
        system = self.prompts["rag_system"]
        user = self.prompts["rag_user"].format(context=context, question=question)
        answer = self.llm.generate(user, system=system)
        return {
            "answer": answer,
            "trace": state.get("trace", []) + [{"node": "generate", "answer_len": len(answer)}],
        }

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
        if iterations < 1:
            state["iterations"] = iterations + 1
            return "rewrite"
        return "stop"
