"""Run Ragas evaluation against the current index.

Steps :
  1. Load Q/A pairs from `results/eval/testset.json`
  2. For each question : run the RAG pipeline → collect answer + contexts
  3. Score with Ragas metrics (Faithfulness, AnswerRelevancy,
     ContextPrecision, ContextRecall)
  4. Save raw + aggregated results to `results/eval/<tag>/`

Notes :
  - We use BGE LOCAL embeddings for Ragas (not Google Cloud) to avoid
    `models/text-embedding-004 NOT_FOUND` errors and stay free.
  - We use a strict RunConfig (max_workers=1) to avoid Gemini quota timeouts.
  - Each metric is evaluated independently so a failure on one doesn't
    nuke the others.

Usage :
    python -m tools.eval.run_ragas
    python -m tools.eval.run_ragas --tag baseline-recursive
    python -m tools.eval.run_ragas --tag semantic-no-rerank --sample 20
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.pipeline import QueryPipeline  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("run_ragas")


# ---------- Judge LLM + embeddings ----------

class _GlobalRateLimiter:
    """Process-wide token bucket. Blocks until the next slot is available."""

    def __init__(self, rpm: int) -> None:
        self._min_interval = 60.0 / max(rpm, 1)
        self._last = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


def _build_judge_llm():
    """
    Build a Ragas-compatible LLM judge with strict client-side rate limiting.

    We subclass ChatGoogleGenerativeAI so EVERY .invoke / .ainvoke call passes
    through the limiter. This prevents the 429 quota storm we saw on the
    free tier of AI Studio.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from ragas.llms import LangchainLLMWrapper

    cfg = get_settings()
    limiter = _GlobalRateLimiter(rpm=cfg.evaluation.judge_rpm)

    class RateLimitedGemini(ChatGoogleGenerativeAI):
        """
        Rate-limited Gemini that ALSO emulates n>1 by calling the model
        sequentially N times. Required because `gemini-3.1-flash-lite` and
        other Lite variants reject candidate_count > 1.
        """

        def _generate(self, messages, *, run_manager=None, stop=None, **kwargs):
            from langchain_core.outputs import ChatResult

            n = kwargs.pop("n", None) or 1
            limiter.acquire()
            if n == 1:
                return super()._generate(messages, run_manager=run_manager, stop=stop, **kwargs)
            # Emulate multiple candidates via sequential calls
            gens = []
            first = super()._generate(messages, run_manager=run_manager, stop=stop, **kwargs)
            gens.extend(first.generations)
            for _ in range(n - 1):
                limiter.acquire()
                more = super()._generate(messages, run_manager=run_manager, stop=stop, **kwargs)
                gens.extend(more.generations)
            return ChatResult(generations=gens, llm_output=first.llm_output)

        async def _agenerate(self, messages, *, run_manager=None, stop=None, **kwargs):
            from langchain_core.outputs import ChatResult

            n = kwargs.pop("n", None) or 1
            limiter.acquire()
            if n == 1:
                return await super()._agenerate(messages, run_manager=run_manager, stop=stop, **kwargs)
            gens = []
            first = await super()._agenerate(messages, run_manager=run_manager, stop=stop, **kwargs)
            gens.extend(first.generations)
            for _ in range(n - 1):
                limiter.acquire()
                more = await super()._agenerate(messages, run_manager=run_manager, stop=stop, **kwargs)
                gens.extend(more.generations)
            return ChatResult(generations=gens, llm_output=first.llm_output)

    judge = RateLimitedGemini(
        model=cfg.evaluation.judge_model,
        google_api_key=cfg.gemini_api_key,
        temperature=0,
        max_output_tokens=1024,
        timeout=120,
    )
    log.info(f"Judge LLM : {cfg.evaluation.judge_model} (rate-limited to {cfg.evaluation.judge_rpm} RPM)")
    return LangchainLLMWrapper(judge)


def _build_judge_embeddings():
    """Use the LOCAL BGE embedder for Ragas — no Google quota / 404 problems."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    cfg = get_settings()
    log.info(f"Ragas embeddings : {cfg.embeddings.model_name} (local, CPU)")
    emb = HuggingFaceEmbeddings(
        model_name=cfg.embeddings.model_name,
        model_kwargs={"device": cfg.embeddings.device},
        encode_kwargs={"normalize_embeddings": cfg.embeddings.normalize},
    )
    return LangchainEmbeddingsWrapper(emb)


# ---------- Metric selection ----------

def _select_metrics(names: list[str]):
    """Return Ragas metric objects matching the configured names."""
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    mapping = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall,
    }
    out = []
    for n in names:
        if n in mapping:
            out.append(mapping[n])
        else:
            log.warning(f"Unknown metric '{n}', skipping.")
    return out


# ---------- Pipeline replay ----------

def run_pipeline_over_testset(testset: list[dict]) -> list[dict]:
    """Replay each question through the pipeline and gather answers + contexts."""
    pipeline = QueryPipeline()

    records: list[dict] = []
    for i, item in enumerate(testset, 1):
        q = item["question"]
        log.info(f"[{i}/{len(testset)}] {q[:90]}")
        t0 = time.time()
        try:
            result = pipeline.ask(q)
        except Exception as e:  # noqa: BLE001
            log.error(f"  Pipeline failed: {e}")
            result = {"answer": "", "sources": [], "trace": []}
        latency = time.time() - t0

        # Extract a usable text per source. Different shapes between simple/agent paths.
        retrieved_contexts: list[str] = []
        for s in result.get("sources", []):
            text = s.get("snippet") or s.get("tool_output_excerpt") or ""
            if text and text.strip():
                retrieved_contexts.append(text)
        if not retrieved_contexts:
            retrieved_contexts = [""]  # Ragas needs non-empty list

        records.append(
            {
                "question": q,
                "answer": result.get("answer", ""),
                "contexts": retrieved_contexts,
                "ground_truth": item.get("ground_truth", ""),
                "route": result.get("route", ""),
                "latency_s": round(latency, 2),
            }
        )
        pipeline.reset_history()  # avoid cross-contamination between questions
    return records


# ---------- Evaluation ----------

def evaluate(records: list[dict]) -> dict:
    """
    Run Ragas metrics over the records.

    To survive Gemini rate limits and individual metric failures, we run each
    metric SEPARATELY with strict concurrency (max_workers=1).
    """
    try:
        from datasets import Dataset
        from ragas import RunConfig, evaluate as ragas_evaluate
    except ImportError as e:
        raise ImportError("`pip install ragas datasets` required.") from e

    cfg = get_settings()
    metric_objs = _select_metrics(cfg.evaluation.metrics)
    if not metric_objs:
        raise RuntimeError("No valid Ragas metrics selected.")

    judge = _build_judge_llm()
    embeddings = _build_judge_embeddings()
    run_config = RunConfig(
        timeout=240,         # generous per-call timeout (Gemma-4 is slow)
        max_retries=3,
        max_wait=60,
        max_workers=1,       # SERIAL — strictly avoid Gemini rate limits
    )

    # Reduce strictness on metrics that use multiple candidates (safe + faster)
    for m in metric_objs:
        if hasattr(m, "strictness"):
            try:
                m.strictness = 1
            except Exception:  # noqa: BLE001
                pass

    dataset = Dataset.from_list(records)
    aggregated: dict[str, float] = {}
    per_row_frames = []

    # Ragas renamed columns over versions ("question" → "user_input")
    # We probe the actual column name once.
    _Q_CANDIDATES = ("question", "user_input", "query", "input")

    for metric in metric_objs:
        log.info(f"Evaluating metric : {metric.name}")
        try:
            result = ragas_evaluate(
                dataset=dataset,
                metrics=[metric],
                llm=judge,
                embeddings=embeddings,
                run_config=run_config,
                raise_exceptions=False,
                show_progress=True,
            )
            df = result.to_pandas()
            if metric.name not in df.columns:
                log.warning(f"Metric {metric.name} did not produce a column. Columns={list(df.columns)}")
                aggregated[metric.name] = float("nan")
                continue

            # Mean ignoring NaN
            score = float(df[metric.name].mean(skipna=True))
            aggregated[metric.name] = score
            log.info(f"  -> {metric.name} = {score:.4f}")

            # Find the question column (varies by Ragas version)
            q_col = next((c for c in _Q_CANDIDATES if c in df.columns), None)
            if q_col:
                per_row_frames.append(
                    df[[q_col, metric.name]].rename(columns={q_col: "question"})
                )
            else:
                # No question column found — keep index-based
                per_row_frames.append(df[[metric.name]].reset_index(drop=True))
        except Exception as e:  # noqa: BLE001
            log.error(f"Metric {metric.name} failed entirely : {e}")
            aggregated[metric.name] = float("nan")

    # Merge per-row results across metrics
    per_row: list[dict] = []
    if per_row_frames:
        try:
            merged = per_row_frames[0]
            for df in per_row_frames[1:]:
                if "question" in merged.columns and "question" in df.columns:
                    merged = merged.merge(df, on="question", how="outer")
                else:
                    merged = merged.join(df, how="outer", rsuffix="_x")
            per_row = merged.to_dict(orient="records")
        except Exception as e:  # noqa: BLE001
            log.warning(f"Per-row merge failed: {e}")
            per_row = []

    return {"aggregated": aggregated, "per_row": per_row}


# ---------- Main ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ragas evaluation.")
    parser.add_argument("--tag", type=str, default=None, help="Subdir name under results/eval/")
    parser.add_argument("--sample", type=int, default=None, help="Subsample the testset")
    parser.add_argument("--testset", type=str, default=None)
    args = parser.parse_args()

    cfg = get_settings()
    testset_path = Path(args.testset) if args.testset else cfg.absolute_path(cfg.evaluation.testset_path)
    if not testset_path.exists():
        log.error(f"Testset not found at {testset_path}. Run generate_testset.py first.")
        return 1

    with testset_path.open("r", encoding="utf-8") as f:
        testset = json.load(f)
    if args.sample:
        testset = testset[: args.sample]
    log.info(f"Loaded {len(testset)} Q/A pairs from {testset_path.name}")

    tag = args.tag or datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = cfg.absolute_path(cfg.evaluation.results_dir) / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Run pipeline
    records = run_pipeline_over_testset(testset)
    with (out_dir / "records.json").open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    log.info(f"Records saved to {out_dir / 'records.json'}")

    # 2) Ragas
    metrics = evaluate(records)
    with (out_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics["aggregated"], f, indent=2)
    with (out_dir / "per_row.json").open("w", encoding="utf-8") as f:
        json.dump(metrics["per_row"], f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 60)
    print(f"RAGAS RESULTS — {tag}")
    print("=" * 60)
    for k, v in metrics["aggregated"].items():
        if v != v:  # NaN check
            print(f"  {k:<25} FAILED")
        else:
            print(f"  {k:<25} {v:.4f}")
    print("=" * 60)
    print(f"Saved : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
