"""Build the vector index from raw documents.

Usage:
    python -m scripts.build_index
    python -m scripts.build_index --source data/raw --reset
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.pipeline import IndexingPipeline  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("build_index")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the agentic-rag vector index.")
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Path to raw documents (file or directory). Defaults to config.paths.data_raw.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the existing collection before indexing.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of chunks (useful for a quick first run).",
    )
    args = parser.parse_args()

    cfg = get_settings()
    source = Path(args.source) if args.source else cfg.absolute_path(cfg.paths.data_raw)

    log.info(f"Building index from: {source}")
    log.info(f"Reset collection: {args.reset}")
    if args.limit:
        log.info(f"Chunk limit       : {args.limit}")

    pipeline = IndexingPipeline()
    stats = pipeline.run(source, reset=args.reset, limit=args.limit)

    log.info("=" * 50)
    log.info(f"Documents loaded : {stats['docs']}")
    log.info(f"Chunks produced  : {stats['chunks']}")
    log.info(f"Vectors in Chroma: {stats['indexed']}")
    log.info(f"BM25 entries     : {stats.get('bm25_indexed', 'N/A')}")
    log.info("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
