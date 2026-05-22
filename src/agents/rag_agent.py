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
    web_results: list[str]   # DuckDuckGo snippets used when KB has no relevant docs
    web_sources: list[dict[str, Any]]  # structured web hits with URL for source display
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

        # 0) Answer from conversation memory when no retrieval is needed
        prior = self.memory.history()[:-1]
        if prior:
            memory_answer = self._answer_from_memory(question, prior)
            if memory_answer is not None:
                log.info("Answered from conversation memory (no retrieval)")
                self.memory.add_assistant(memory_answer)
                return {
                    "answer": memory_answer,
                    "route": "memory",
                    "sources": [],
                    "trace": [{"node": "memory_check", "answered": True}],
                }

        # 1) OOD check — one LLM call, blocks the whole pipeline if out of domain
        if self._check_out_of_domain(question):
            log.info("OOD detected — skipping pipeline")
            ood_answer = (
                "Cette question dépasse le domaine de la knowledge base "
                "(Data Science / Machine Learning / IA). "
                "Je ne peux pas y répondre avec les ressources disponibles."
            )
            self.memory.add_assistant(ood_answer)
            return {
                "answer": ood_answer,
                "route": "out_of_domain",
                "sources": [],
                "trace": [{"node": "ood_check", "result": "out_of_domain"}],
            }

        # 2) Route
        route = self.router.route(question)
        log.info(f"Routing → {route}")

        # 3) Dispatch — each branch falls back to the other on failure
        prior_history = self.memory.history()[:-1]  # exclude the current user turn
        if route == "agent":
            try:
                # Rewrite the question with conversation history before sending to ReAct
                rewritten = self._rewrite_question(question, prior_history)
                result = self.react_agent.run(rewritten, history=prior_history)
                result["route"] = "agent"
            except Exception as e:  # noqa: BLE001
                log.warning(f"Agent route failed ({type(e).__name__}: {e}), falling back to simple")
                result = self._run_simple(question)
                result["route"] = "simple_fallback"
        else:
            try:
                result = self._run_simple(question)
                result["route"] = "simple"
            except Exception as e:  # noqa: BLE001
                log.warning(f"Simple route failed ({type(e).__name__}: {e}), falling back to agent")
                result = self.react_agent.run(question, history=prior_history)
                result["route"] = "agent_fallback"

        self.memory.add_assistant(result.get("answer", ""))
        return result

    # ---------- OOD check ----------

    def _check_out_of_domain(self, question: str) -> bool:
        """Return True if the question is clearly outside the DS/ML/AI domain.

        One LLM call with a minimal yes/no prompt. Returns False on any failure
        so the pipeline always continues in case of doubt.
        """
        try:
            system = self.prompts["ood_check_system"]
            verdict = self.llm.generate(question, system=system).strip().lower()
            first_word = verdict.split()[0].strip(".,!?\"'") if verdict else "yes"
            is_ood = first_word == "no"
            log.debug(f"OOD check → '{first_word}' (ood={is_ood})")
            return is_ood
        except Exception as e:  # noqa: BLE001
            log.warning(f"OOD check failed ({e}), assuming in-domain")
            return False  # fail-safe : on laisse passer en cas d'erreur

    # ---------- Memory check ----------

    def _answer_from_memory(self, question: str, history: list[dict]) -> str | None:
        """Return an answer if the question can be resolved from conversation history alone.

        Returns the answer string, or None if retrieval is needed.
        """
        history_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in history)
        system = self.prompts["memory_check_system"]
        user = self.prompts["memory_check_user"].format(
            history=history_text, question=question
        )
        try:
            response = self.llm.generate(user, system=system).strip()
        except Exception as e:  # noqa: BLE001
            log.warning(f"Memory check failed: {e}")
            return None
        if response.upper().startswith("MEMORY:"):
            return response[len("MEMORY:"):].strip()
        return None

    # ---------- Query rewrite (shared between simple and agent paths) ----------

    def _rewrite_question(self, question: str, history: list[dict]) -> str:
        """Rewrite question into a standalone query using conversation history.

        Returns the original question unchanged if:
        - There is no prior assistant turn (first message in session)
        - The rewrite LLM call fails
        """
        has_prior_assistant = any(t["role"] == "assistant" for t in history)
        if not has_prior_assistant:
            return question  # first turn — nothing to rewrite

        history_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in history)
        system = self.prompts["reformulate_system"]
        user = f"Conversation history:\n{history_text}\n\nNew question: {question}"
        try:
            rewritten = self.llm.generate(user, system=system).strip()
            log.debug(f"Rewrite: '{question[:60]}' → '{rewritten[:60]}'")
            return rewritten or question
        except Exception as e:  # noqa: BLE001
            log.warning(f"Rewrite failed: {e}")
            return question

    # ---------- Simple (CRAG-light) ----------

    def _run_simple(self, question: str) -> dict[str, Any]:
        initial: RagState = {
            "question": question,
            "rewritten_question": question,
            "iterations": 0,
            "trace": [],
        }
        final: RagState = self.simple_graph.invoke(initial)

        relevant_docs = final.get("relevant_documents", [])
        kb_sources = [
            {
                "id": d.id,
                "source": d.metadata.get("source", d.id),
                "book_title": d.metadata.get("book_title", ""),
                "page": d.metadata.get("page", ""),
                "score": d.score,
                "snippet": d.text,
            }
            for d in relevant_docs
        ]
        sources = kb_sources + final.get("web_sources", [])
        return {
            "answer": final.get("answer", ""),
            "sources": sources,
            "contexts": [d.text for d in relevant_docs],
            "trace": final.get("trace", []),
            "iterations": final.get("iterations", 0),
        }

    # ---------- Graph construction (CRAG-light) ----------

    def _build_simple_graph(self):
        g = StateGraph(RagState)
        g.add_node("rewrite", self._node_rewrite)
        g.add_node("retrieve", self._node_retrieve)
        g.add_node("grade", self._node_grade)
        g.add_node("web_fallback", self._node_web_fallback)
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
            {"generate": "generate", "rewrite": "rewrite", "web_fallback": "web_fallback"},
        )
        g.add_edge("web_fallback", "generate")
        g.add_edge("generate", END)
        return g.compile()

    # ---------- Nodes ----------

    def _node_rewrite(self, state: RagState) -> RagState:
        history = self.memory.history()
        # Exclude the current user turn from the history passed to rewrite
        prior = history[:-1] if history and history[-1]["role"] == "user" else history
        rewritten = self._rewrite_question(state["question"], prior)
        skipped = rewritten == state["question"]
        return {
            "rewritten_question": rewritten,
            "trace": state.get("trace", []) + [
                {"node": "rewrite", "skipped": skipped, "output": rewritten[:120]}
            ],
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
        new_iters = state.get("iterations", 0) + 1  # increment HERE (state is immutable elsewhere)
        if not self.cfg.enable_grading or not docs:
            return {
                "relevant_documents": docs,
                "iterations": new_iters,
                "trace": state.get("trace", []) + [{"node": "grade", "skipped": True}],
            }
        question = state.get("rewritten_question") or state["question"]
        decisions = self._grade_batch(question, [d.text for d in docs])
        keep = [d for d, relevant in zip(docs, decisions) if relevant]
        log.info(f"Graded relevant: {len(keep)}/{len(docs)} (iter {new_iters})")
        return {
            "relevant_documents": keep,
            "iterations": new_iters,
            "trace": state.get("trace", []) + [
                {"node": "grade", "kept": len(keep), "total": len(docs), "iter": new_iters}
            ],
        }

    def _node_web_fallback(self, state: RagState) -> RagState:
        if not self.cfg.enable_web_fallback:
            return {
                "web_results": [],
                "trace": state.get("trace", []) + [{"node": "web_fallback", "skipped": True}],
            }
        query = state.get("rewritten_question") or state["question"]
        try:
            from ddgs import DDGS  # optional dependency
            with DDGS() as ddgs:
                hits = ddgs.text(query, max_results=4)
            valid_hits = [h for h in hits if h.get("body")]
            snippets = [f"{h['title']}: {h['body']}" for h in valid_hits]
            web_sources = [
                {
                    "source": h.get("href", ""),
                    "book_title": h.get("title", "Web"),
                    "url": h.get("href", ""),
                    "page": "",
                    "score": 0.0,
                    "snippet": h.get("body", ""),
                }
                for h in valid_hits
            ]
            log.info(f"Web fallback: {len(snippets)} snippets for '{query[:60]}'")
        except Exception as e:  # noqa: BLE001
            log.warning(f"Web search fallback failed: {e}")
            snippets = []
            web_sources = []
        return {
            "web_results": snippets,
            "web_sources": web_sources,
            "trace": state.get("trace", []) + [{"node": "web_fallback", "n_results": len(snippets)}],
        }

    def _node_generate(self, state: RagState) -> RagState:
        # Use relevant_documents if non-empty; do NOT fall back to raw documents
        # (they were graded irrelevant). Web results take priority when KB is empty.
        relevant = state.get("relevant_documents") or []
        web_results = state.get("web_results", [])
        question = state.get("rewritten_question") or state["question"]

        if not relevant and not web_results:
            return {
                "answer": "I could not find relevant information in the knowledge base.",
                "trace": state.get("trace", []) + [{"node": "generate", "no_context": True}],
            }

        if relevant:
            context = "\n\n---\n\n".join(
                f"[{d.metadata.get('book_title') or d.metadata.get('source', d.id)}"
                + (f", p.{d.metadata.get('page')}" if d.metadata.get('page') else "")
                + f"]\n{d.text}"
                for d in relevant
            )
        else:
            context = "\n\n---\n\n".join(f"[Web]\n{r}" for r in web_results)

        source = "web" if not relevant else "kb"
        system = self.prompts["web_rag_system"] if source == "web" else self.prompts["rag_system"]
        user = self.prompts["rag_user"].format(context=context, question=question)
        answer = self.llm.generate(user, system=system)
        return {
            "answer": answer,
            "trace": state.get("trace", []) + [{"node": "generate", "answer_len": len(answer), "source": source}],
        }

    def _grade_batch(self, question: str, documents: list[str]) -> list[bool]:
        numbered = "\n\n".join(
            f"Document {i + 1}:\n{doc[:2000]}" for i, doc in enumerate(documents)
        )
        system = self.prompts["grade_batch_system"]
        user = self.prompts["grade_batch_user"].format(
            question=question, documents=numbered, n=len(documents)
        )
        try:
            response = self.llm.generate(user, system=system).strip()
            lines = [ln.strip().lower() for ln in response.splitlines() if ln.strip()]
            decisions: list[bool] = []
            for line in lines[: len(documents)]:
                decisions.append("yes" in line)
            # Pad with False (discard) if model returned a summary instead of per-doc answers
            while len(decisions) < len(documents):
                decisions.append(False)
            return decisions
        except Exception as e:  # noqa: BLE001
            log.warning(f"Batch grader failed, treating all docs as not relevant: {e}")
            return [False] * len(documents)

    def _decide_after_grade(self, state: RagState) -> str:
        """Pure routing decision, no state mutation here (mutation lives in nodes)."""
        n_relevant = len(state.get("relevant_documents", []))
        iterations = state.get("iterations", 0)
        max_iters = max(1, self.cfg.max_iterations // 3)  # ~2 retries by default
        if n_relevant >= 1:
            return "generate"
        if iterations < max_iters:
            return "rewrite"
        # KB exhausted — try web search before generating from empty context
        return "web_fallback"
