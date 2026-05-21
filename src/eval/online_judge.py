"""Async online LLM Judge — scores ~15 % of live user queries in the background.

Metrics (standard RAG):
  - faithfulness    (0-1): every claim in the answer is grounded in the retrieved context
  - answer_relevancy (0-1): the answer directly addresses the question

The judge uses a *separate* LLM (configured under online_eval.judge in config.yaml)
to avoid self-scoring bias — the RAG model should never grade its own outputs.

Usage (inside QueryPipeline):
    judge = OnlineJudge()
    result = agent.run(question)
    judge.maybe_evaluate(
        question,
        result["answer"],
        contexts=result.get("contexts", []),
    )

Scores are appended to results/logs/runtime_quality.jsonl.
A one-line summary is printed to stdout after each completed evaluation.
"""
from __future__ import annotations

import atexit
import json
import random
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_prompts, get_settings
from src.utils import get_logger

log = get_logger(__name__)

_FAITHFULNESS_RE = re.compile(r"FAITHFULNESS\s*:\s*([01](?:\.\d+)?)", re.IGNORECASE)
_RELEVANCY_RE = re.compile(r"ANSWER_RELEVANCY\s*:\s*([01](?:\.\d+)?)", re.IGNORECASE)
_REASON_RE = re.compile(r"REASON\s*:\s*(.+)", re.IGNORECASE)


def _build_judge_llm(cfg):
    """Build the LangChain chat model for the judge from online_eval.judge config."""
    judge_cfg = cfg.online_eval.judge
    if judge_cfg.provider == "groq":
        from langchain_groq import ChatGroq
        groq_keys = cfg.get_groq_keys()
        if not groq_keys:
            raise RuntimeError(
                "OnlineJudge requires a Groq key. Set GROQ_API_KEY or GROQ_API_KEYS in .env."
            )
        return ChatGroq(
            model=judge_cfg.model,
            api_key=groq_keys[0],
            temperature=0,
            max_tokens=256,
        )
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        if not cfg.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing.")
        return ChatGoogleGenerativeAI(
            model=judge_cfg.model,
            google_api_key=cfg.gemini_api_key,
            temperature=0,
            max_output_tokens=256,
        )


class OnlineJudge:
    """Non-blocking quality sampler: submits eval tasks to a background thread pool.

    The judge is intentionally separate from the RAG LLM to avoid self-scoring bias.
    Provider and model are read from `online_eval.judge` in config.yaml.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._enabled = cfg.online_eval.enabled
        self._sample_rate = cfg.online_eval.sample_rate
        self._log_path = cfg.absolute_path(cfg.online_eval.log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._prompts = get_prompts()
        self._llm = _build_judge_llm(cfg)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="online_judge")
        self._faithfulness_scores: list[float] = []
        self._relevancy_scores: list[float] = []
        self._lock = threading.Lock()
        log.info(
            f"OnlineJudge ready: provider={cfg.online_eval.judge.provider} "
            f"model={cfg.online_eval.judge.model}"
        )
        atexit.register(self.shutdown)

    # ── Public ────────────────────────────────────────────────────────────────

    def maybe_evaluate(
        self,
        question: str,
        answer: str,
        contexts: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Future[None] | None":
        """Submit an eval task with probability `sample_rate`. Returns the Future (or None)."""
        if not self._enabled or not answer.strip():
            return None
        if random.random() > self._sample_rate:
            return None
        return self._executor.submit(self._evaluate, question, answer, contexts or [], metadata or {})

    def shutdown(self) -> None:
        """Graceful shutdown — waits for any in-flight evaluations to complete."""
        self._executor.shutdown(wait=True)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _call_llm(self, system: str, user: str) -> str:
        msgs = [SystemMessage(content=system), HumanMessage(content=user)]
        result = self._llm.invoke(msgs)
        content = result.content
        return content if isinstance(content, str) else str(content)

    def _evaluate(self, question: str, answer: str, contexts: list[str], metadata: dict[str, Any]) -> None:
        try:
            # Truncate each context chunk to avoid blowing the token budget
            context_text = "\n\n---\n\n".join(c[:800] for c in contexts) if contexts else "(no context)"

            system = self._prompts["judge_online_system"]
            user = self._prompts["judge_online_user"].format(
                question=question,
                context=context_text,
                answer=answer,
            )
            raw = self._call_llm(system, user).strip()
            faithfulness, relevancy = self._parse_scores(raw)
            reason_m = _REASON_RE.search(raw)
            reason = reason_m.group(1).strip() if reason_m else ""

            entry: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "question": question[:300],
                "answer_preview": answer[:400],
                "faithfulness": faithfulness,
                "answer_relevancy": relevancy,
                "reason": reason,
                "raw_response": raw[:500],
                **metadata,
            }

            with self._lock:
                if faithfulness == faithfulness:  # not NaN
                    self._faithfulness_scores.append(faithfulness)
                if relevancy == relevancy:
                    self._relevancy_scores.append(relevancy)
                with self._log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

            self._print_summary(faithfulness, relevancy, reason)

        except Exception as e:  # noqa: BLE001
            log.warning(f"OnlineJudge evaluation failed: {e}")

    @staticmethod
    def _parse_scores(response: str) -> tuple[float, float]:
        faith_m = _FAITHFULNESS_RE.search(response)
        rel_m = _RELEVANCY_RE.search(response)
        faithfulness = float(faith_m.group(1)) if faith_m else float("nan")
        relevancy = float(rel_m.group(1)) if rel_m else float("nan")
        return faithfulness, relevancy

    def _print_summary(self, latest_faith: float, latest_rel: float, reason: str = "") -> None:
        with self._lock:
            valid_faith = [s for s in self._faithfulness_scores if s == s]
            valid_rel = [s for s in self._relevancy_scores if s == s]
        if max(len(valid_faith), len(valid_rel)) == 0:
            return
        faith_str = f"{latest_faith:.2f}" if latest_faith == latest_faith else "N/A"
        rel_str = f"{latest_rel:.2f}" if latest_rel == latest_rel else "N/A"
        reason_str = f"  reason={reason[:100]}" if reason and reason.upper() != "OK" else ""
        print(
            f"\n[OnlineJudge] faithfulness={faith_str}  relevancy={rel_str}{reason_str}\n",
            flush=True,
        )
