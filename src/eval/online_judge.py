"""Async online LLM Judge — scores ~15 % of live user questions in the background.

Usage (inside QueryPipeline):
    judge = OnlineJudge(llm)
    result = agent.run(question)
    judge.maybe_evaluate(question, result["answer"])   # fire-and-forget

Scores are appended to results/logs/runtime_quality.jsonl.
A one-line summary is printed to stdout after each completed evaluation.
"""
from __future__ import annotations

import atexit
import json
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import get_prompts, get_settings
from src.llm import GeminiClient
from src.utils import get_logger

log = get_logger(__name__)

_SCORE_RE = re.compile(r"SCORE\s*:\s*([0-5](?:\.\d)?)", re.IGNORECASE)


class OnlineJudge:
    """Non-blocking quality sampler: submits eval tasks to a background thread pool."""

    def __init__(self, llm: GeminiClient) -> None:
        self.llm = llm
        cfg = get_settings()
        self._enabled = cfg.online_eval.enabled
        self._sample_rate = cfg.online_eval.sample_rate
        self._log_path = cfg.absolute_path(cfg.online_eval.log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._prompts = get_prompts()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="online_judge")
        self._scores: list[float] = []
        self._lock = threading.Lock()
        atexit.register(self.shutdown)

    # ── Public ────────────────────────────────────────────────────────────────

    def maybe_evaluate(self, question: str, answer: str, metadata: dict[str, Any] | None = None) -> None:
        """Fire-and-forget: submit an eval task with probability `sample_rate`."""
        if not self._enabled or not answer.strip():
            return
        if random.random() > self._sample_rate:
            return
        self._executor.submit(self._evaluate, question, answer, metadata or {})

    def shutdown(self) -> None:
        """Graceful shutdown — waits for any in-flight evaluations to complete."""
        self._executor.shutdown(wait=True)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _evaluate(self, question: str, answer: str, metadata: dict[str, Any]) -> None:
        try:
            system = self._prompts["judge_online_system"]
            user = self._prompts["judge_online_user"].format(
                question=question, answer=answer
            )
            raw = self.llm.generate(user, system=system).strip()
            score = self._parse_score(raw)

            entry: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "question": question[:300],
                "answer_preview": answer[:400],
                "score": score,
                "raw_response": raw[:500],
                **metadata,
            }

            with self._lock:
                if score == score:  # not NaN
                    self._scores.append(score)
                with self._log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

            self._print_summary(score)

        except Exception as e:  # noqa: BLE001
            log.warning(f"OnlineJudge evaluation failed: {e}")

    @staticmethod
    def _parse_score(response: str) -> float:
        m = _SCORE_RE.search(response)
        return float(m.group(1)) if m else float("nan")

    def _print_summary(self, latest: float) -> None:
        with self._lock:
            valid = [s for s in self._scores if s == s]
        if not valid:
            return
        avg = sum(valid) / len(valid)
        score_str = f"{latest:.0f}/5" if latest == latest else "N/A"
        print(
            f"\n[OnlineJudge] latest={score_str}  avg={avg:.2f}/5  "
            f"n={len(valid)}  log={self._log_path}\n",
            flush=True,
        )
