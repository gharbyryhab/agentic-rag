"""Comparative benchmark : recursive vs semantic chunking.

For each chunking strategy :
  1. Rebuild the index from scratch
  2. Run Ragas evaluation on the same testset
  3. Capture timing + chunk count + Ragas metrics

Generates a comparison report at `results/eval/comparison_<timestamp>/`.

Usage :
    python -m tools.eval.compare_strategies --strategies recursive,semantic
    python -m tools.eval.compare_strategies --strategies semantic --sample 20

⚠️  Each strategy triggers a FULL reindexing (`--reset`). Plan accordingly :
    - recursive   : ~4-5h on i3 CPU
    - semantic    : ~14-20h on i3 CPU
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import CONFIG_PATH, get_settings  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("compare_strategies")


def _load_yaml() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_yaml(data: dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def _set_chunking_strategy(strategy: str) -> None:
    """Mutate config.yaml in place to switch chunking strategy."""
    cfg = _load_yaml()
    cfg["chunking"]["strategy"] = strategy
    _save_yaml(cfg)
    log.info(f"config.yaml updated → chunking.strategy = {strategy}")


def _run_subprocess(cmd: list[str], cwd: Path) -> tuple[int, float]:
    """Run a command and return (return_code, duration_seconds)."""
    log.info("$ " + " ".join(cmd))
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode, time.time() - t0


def _backup_vector_store(strategy: str) -> Path | None:
    """Backup the current vector_store/ before nuking it for the next run."""
    cfg = get_settings()
    src = cfg.absolute_path("vector_store")
    if not src.exists():
        return None
    dst = src.parent / f"vector_store_backup_{strategy}"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    log.info(f"Backup : {src} → {dst}")
    return dst


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text().strip())
    except Exception:  # noqa: BLE001
        return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare chunking strategies.")
    parser.add_argument(
        "--strategies",
        type=str,
        default="recursive,semantic",
        help="Comma-separated list among {recursive, semantic}",
    )
    parser.add_argument("--sample", type=int, default=None, help="Subsample testset")
    parser.add_argument("--skip-build", action="store_true", help="Skip indexing (use existing).")
    args = parser.parse_args()

    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    cfg = get_settings()
    out_root = cfg.absolute_path(cfg.evaluation.results_dir) / f"comparison_{datetime.now():%Y%m%d_%H%M%S}"
    out_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict] = {}

    for strategy in strategies:
        log.info("=" * 70)
        log.info(f"STRATEGY : {strategy}")
        log.info("=" * 70)

        record: dict = {"strategy": strategy}

        # 1) Switch config + rebuild
        if not args.skip_build:
            _set_chunking_strategy(strategy)
            rc, build_secs = _run_subprocess(
                [sys.executable, "-m", "scripts.build_index", "--reset"],
                cwd=ROOT,
            )
            record["build_returncode"] = rc
            record["build_seconds"] = round(build_secs, 1)
            if rc != 0:
                log.error(f"Build failed for {strategy} (rc={rc}), skipping eval.")
                summary[strategy] = record
                continue

        # 2) Snapshot collection sizes
        from src.vector_store import BM25Store, ChromaStore

        record["chroma_vectors"] = ChromaStore().count()
        record["bm25_entries"] = BM25Store().count()

        # 3) Run Ragas
        tag = f"{strategy}_{datetime.now():%H%M%S}"
        ragas_cmd = [sys.executable, "-m", "tools.eval.run_ragas", "--tag", tag]
        if args.sample:
            ragas_cmd += ["--sample", str(args.sample)]
        rc, ragas_secs = _run_subprocess(ragas_cmd, cwd=ROOT)
        record["ragas_returncode"] = rc
        record["ragas_seconds"] = round(ragas_secs, 1)

        # 4) Load metrics
        metrics_path = cfg.absolute_path(cfg.evaluation.results_dir) / tag / "metrics.json"
        if metrics_path.exists():
            record["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
        else:
            record["metrics"] = {}

        # 5) Backup vector_store (so user can re-run without re-indexing)
        backup = _backup_vector_store(strategy)
        if backup:
            record["backup"] = str(backup)

        summary[strategy] = record

    # ----- Comparison report -----
    report_path = out_root / "comparison.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    metric_names = sorted({m for r in summary.values() for m in r.get("metrics", {})})
    header = f"{'strategy':<14} {'chunks':>8} {'build_s':>10} " + " ".join(f"{n[:14]:>15}" for n in metric_names)
    print(header)
    print("-" * len(header))
    for s, r in summary.items():
        row = (
            f"{s:<14} "
            f"{r.get('chroma_vectors', 0):>8} "
            f"{r.get('build_seconds', 0):>10.1f} "
            + " ".join(
                f"{(r.get('metrics', {}).get(n, float('nan'))):>15.4f}" for n in metric_names
            )
        )
        print(row)
    print("=" * 80)
    print(f"Report saved → {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
