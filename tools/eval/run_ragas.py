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
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.pipeline import QueryPipeline  # noqa: E402
from src.utils import get_logger  # noqa: E402
from tools.eval._rate_limiter import (  # noqa: E402
    build_rotating_groq,
    build_token_aware_gemini,
)

log = get_logger("run_ragas")


# ---------- Judge LLM + embeddings ----------

def _build_judge_llm():
    """
    Build a Ragas-compatible LLM judge with :
      - MULTI-KEY ROTATION on TPD exhaustion (Groq) → uses all keys in
        GROQ_API_KEYS, matching the synthesizer's setup.
      - TPM/RPM token bucket → smooth bursts, avoid 429.
      - max_tokens=2048 → faithfulness produces long claim-decomposition JSON.

    The previous version used a single-key wrapper without rotation, which
    caused TimeoutError when the active key's TPD got exhausted mid-evaluation.
    """
    from ragas.llms import LangchainLLMWrapper

    cfg = get_settings()
    judge_cfg = cfg.evaluation.judge

    if judge_cfg.provider == "groq":
        groq_keys = cfg.get_groq_keys()
        if not groq_keys:
            raise RuntimeError(
                "No Groq keys found. Set GROQ_API_KEY (single) or "
                "GROQ_API_KEYS (comma-separated list) in .env. "
                "Get free keys at https://console.groq.com/keys"
            )
        judge = build_rotating_groq(
            model=judge_cfg.model,
            api_keys=groq_keys,
            rpm=judge_cfg.rpm,
            tpm=judge_cfg.tpm,
            temperature=0,
            # 2048 needed for faithfulness : the Judge decomposes the answer
            # into atomic claims, producing long structured JSON. 1024 was
            # causing LLMDidNotFinishException mid-evaluation.
            max_tokens=2048,
            timeout=120,
        )
        log.info(
            f"Judge LLM : groq/{judge_cfg.model} with {len(groq_keys)} key(s) "
            f"(rpm={judge_cfg.rpm}, tpm={judge_cfg.tpm}, max_tokens=2048, "
            f"rotation={'enabled' if len(groq_keys) >= 2 else 'disabled (1 key)'})"
        )
        return LangchainLLMWrapper(judge)

    # ── Gemini fallback ─────────────────────────────────────────────────────
    judge = build_token_aware_gemini(
        model=judge_cfg.model,
        api_key=cfg.gemini_api_key,
        rpm=judge_cfg.rpm,
        tpm=0,   # Gemini has no public TPM cap on free tier
        temperature=0,
        max_output_tokens=2048,
        timeout=120,
    )
    log.info(f"Judge LLM : gemini/{judge_cfg.model} (rpm={judge_cfg.rpm})")
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

def evaluate(records: list[dict], skip_metrics: dict[str, float] | None = None) -> dict:
    """
    Run Ragas metrics over the records.

    To survive Groq/Gemini rate limits and individual metric failures, we run
    each metric SEPARATELY with strict concurrency (max_workers=1).

    Args:
        records: list of {question, answer, contexts, ground_truth, ...} dicts.
        skip_metrics: dict of metric_name → score that are already computed.
            These metrics are skipped (resume mode). Pass {} or None to
            recompute everything.
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

    skip_metrics = skip_metrics or {}
    # Filter out metrics we already have a valid score for
    remaining = [m for m in metric_objs if m.name not in skip_metrics]
    if len(remaining) < len(metric_objs):
        skipped_names = [m.name for m in metric_objs if m.name in skip_metrics]
        log.info(f"♻️  Skipping {len(skipped_names)} already-computed metric(s): {skipped_names}")
        metric_objs = remaining
    if not metric_objs:
        log.info("All metrics already computed (resume mode). Nothing to do.")
        return {"aggregated": dict(skip_metrics), "per_row": []}

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
    parser.add_argument(
        "--from-records",
        type=str,
        default=None,
        help="Path to an existing records.json. Skips the pipeline replay and "
             "directly computes the metrics. Useful when only the metric step "
             "failed in a previous run (e.g. judge LLM 429 storm).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute ALL metrics even if some are already in metrics.json. "
             "Default behavior : skip already-computed metrics (resume mode).",
    )
    args = parser.parse_args()

    cfg = get_settings()

    # ═══════════════════════════════════════════════════════════════════════
    # FROM-RECORDS MODE : skip pipeline, just (re)compute metrics
    # ═══════════════════════════════════════════════════════════════════════
    if args.from_records:
        records_path = Path(args.from_records)
        if not records_path.exists():
            log.error(f"Records file not found : {records_path}")
            return 1
        with records_path.open("r", encoding="utf-8") as f:
            records = json.load(f)
        log.info(f"♻️  Loaded {len(records)} records from {records_path}")

        # Reuse the records' parent directory as output dir → metrics land
        # next to the records they were computed from.
        out_dir = records_path.parent
        log.info(f"Output directory : {out_dir} (next to existing records)")

        # Load already-computed metrics if any (for resume)
        existing_metrics = _load_existing_metrics(out_dir, force=args.force)
        if existing_metrics:
            already_done = [k for k, v in existing_metrics.items() if v == v]
            log.info(
                f"♻️  Resuming : {len(already_done)} metric(s) already computed "
                f"({', '.join(already_done) or 'none'}). Use --force to recompute."
            )

        metrics = evaluate(records, skip_metrics=existing_metrics)
        # Merge with existing : existing wins unless --force
        if existing_metrics and not args.force:
            for k, v in existing_metrics.items():
                if v == v and (k not in metrics["aggregated"] or
                               metrics["aggregated"][k] != metrics["aggregated"][k]):
                    metrics["aggregated"][k] = v

        _save_metrics(out_dir, metrics)
        _print_final(out_dir.name, metrics["aggregated"], out_dir)
        return 0

    # ═══════════════════════════════════════════════════════════════════════
    # FULL MODE : pipeline replay + metrics
    # ═══════════════════════════════════════════════════════════════════════
    testset_path = Path(args.testset) if args.testset else cfg.absolute_path(cfg.evaluation.testset_path)
    if not testset_path.exists():
        log.error(f"Testset not found at {testset_path}. Run generate_testset.py first.")
        return 1

    with testset_path.open("r", encoding="utf-8") as f:
        testset = json.load(f)
    if args.sample:
        testset = testset[: args.sample]
    log.info(f"Loaded {len(testset)} Q/A pairs from {testset_path.name}")

    # Build a self-documenting tag : <base>_<chunking_strategy>_<YYYYMMDD>_<HHMMSS>
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chunking_strategy = cfg.chunking.strategy
    base = args.tag or "run"
    tag = f"{base}_{chunking_strategy}_{timestamp}"
    out_dir = cfg.absolute_path(cfg.evaluation.results_dir) / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info(f"Output directory : {out_dir}")

    # Snapshot the active config so the run is fully reproducible later.
    try:
        import yaml as _yaml
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
        with config_path.open("r", encoding="utf-8") as f:
            full_config = _yaml.safe_load(f)
        config_snapshot = {
            section: full_config.get(section)
            for section in ("chunking", "filters", "header_footer", "retrieval",
                            "llm", "agent", "evaluation")
            if section in full_config
        }
        config_snapshot["_meta"] = {
            "tag": tag,
            "base_tag": base,
            "chunking_strategy": chunking_strategy,
            "timestamp": timestamp,
            "sample_size": len(testset),
            "testset_source": str(testset_path.name),
        }
        with (out_dir / "config_snapshot.yaml").open("w", encoding="utf-8") as f:
            _yaml.safe_dump(config_snapshot, f, sort_keys=False, default_flow_style=False)
        log.info(f"Config snapshot saved to {out_dir / 'config_snapshot.yaml'}")
    except Exception as e:  # noqa: BLE001
        log.warning(f"Could not save config snapshot: {e}")

    # 1) Run pipeline
    records = run_pipeline_over_testset(testset)
    with (out_dir / "records.json").open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    log.info(f"Records saved to {out_dir / 'records.json'}")

    # 2) Ragas
    metrics = evaluate(records)
    _save_metrics(out_dir, metrics)
    _print_final(tag, metrics["aggregated"], out_dir)
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for resume / from-records mode
# ──────────────────────────────────────────────────────────────────────────────

def _load_existing_metrics(out_dir: Path, force: bool) -> dict[str, float]:
    """Read metrics.json from a previous (partial) run. Returns {} if --force
    or no metrics.json yet."""
    if force:
        return {}
    metrics_path = out_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    try:
        with metrics_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Filter out NaN (failed previously, want to retry)
        return {k: float(v) for k, v in data.items() if isinstance(v, (int, float)) and v == v}
    except Exception as e:  # noqa: BLE001
        log.warning(f"Could not read existing metrics.json: {e}")
        return {}


def _save_metrics(out_dir: Path, metrics: dict) -> None:
    """Save metrics.json + per_row.json atomically."""
    with (out_dir / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics["aggregated"], f, indent=2)
    with (out_dir / "per_row.json").open("w", encoding="utf-8") as f:
        json.dump(metrics["per_row"], f, ensure_ascii=False, indent=2, default=str)


def _print_final(tag: str, aggregated: dict, out_dir: Path) -> None:
    """Pretty-print the final metric summary."""
    print("\n" + "=" * 60)
    print(f"RAGAS RESULTS — {tag}")
    print("=" * 60)
    for k, v in aggregated.items():
        if not isinstance(v, (int, float)) or v != v:  # NaN check
            print(f"  {k:<25} FAILED")
        else:
            print(f"  {k:<25} {v:.4f}")
    print("=" * 60)
    print(f"Saved : {out_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
