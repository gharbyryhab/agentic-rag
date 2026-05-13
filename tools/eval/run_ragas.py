"""Run Ragas evaluation against the current index.

Steps :
  1. Load Q/A pairs from `results/eval/testset.json`
  2. For each question : run the RAG pipeline → collect answer + contexts
  3. Score with Ragas metrics (Faithfulness, AnswerRelevancy,
     ContextPrecision, ContextRecall)
  4. Save raw + aggregated results to `results/eval/<tag>/`

Usage :
    python -m tools.eval.run_ragas
    python -m tools.eval.run_ragas --tag baseline-recursive
    python -m tools.eval.run_ragas --tag semantic-no-rerank --sample 20
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.pipeline import QueryPipeline  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("run_ragas")


def _build_judge():
    """Build the LLM judge + embeddings used by Ragas metrics."""
    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
        GoogleGenerativeAIEmbeddings,
    )

    cfg = get_settings()
    judge = ChatGoogleGenerativeAI(
        model=cfg.evaluation.judge_model,
        google_api_key=cfg.gemini_api_key,
        temperature=0,
    )
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=cfg.gemini_api_key,
    )
    return judge, embeddings


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

        retrieved_contexts = [s.get("snippet") or s.get("tool_output_excerpt") or "" for s in result.get("sources", [])]
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


def evaluate(records: list[dict]) -> dict:
    """Run Ragas metrics over the records and return aggregated + per-row results."""
    try:
        from datasets import Dataset
        from ragas import evaluate as ragas_evaluate
    except ImportError as e:
        raise ImportError("`pip install ragas datasets` required.") from e

    cfg = get_settings()
    metrics = _select_metrics(cfg.evaluation.metrics)
    if not metrics:
        raise RuntimeError("No valid Ragas metrics selected.")

    judge, embeddings = _build_judge()

    dataset = Dataset.from_list(records)
    log.info(f"Running Ragas on {len(records)} samples with {len(metrics)} metrics…")
    result = ragas_evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge,
        embeddings=embeddings,
        raise_exceptions=False,
    )
    df = result.to_pandas()
    aggregated = {
        m.name: float(df[m.name].mean(skipna=True))
        for m in metrics
        if m.name in df.columns
    }
    return {"aggregated": aggregated, "per_row": df.to_dict(orient="records")}


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
        print(f"  {k:<25} {v:.4f}")
    print("=" * 60)
    print(f"Saved : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
