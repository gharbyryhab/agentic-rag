"""Ask a question to the agentic RAG from the command line.

Usage:
    python -m scripts.query "What is the difference between LoRA and full fine-tuning?"
    python -m scripts.query --interactive
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import QueryPipeline  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("query")


def _print_result(result: dict) -> None:
    from pathlib import Path
    
    print("\n" + "=" * 70)
    print("RÉPONSE")
    print("=" * 70)
    print(result["answer"])
    
    if result["sources"]:
        print("\n" + "-" * 70)
        print(f"SOURCES ({len(result['sources'])})")
        print("-" * 70)
        for i, s in enumerate(result["sources"], 1):
            # Afficher seulement le nom du fichier, pas le chemin complet
            source_name = Path(s['source']).name
            print(f"{i}. [{s['score']:.3f}] {source_name}")
            print(f"   {s['snippet'][:120]}...")
    print("=" * 70 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the agentic RAG.")
    parser.add_argument("question", nargs="?", help="The question to ask.")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Open an interactive REPL."
    )
    args = parser.parse_args()

    pipeline = QueryPipeline()

    if args.interactive:
        print("Agentic RAG — interactive mode. Type 'exit' to quit, 'reset' to clear history.\n")
        while True:
            try:
                q = input("You> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q:
                continue
            if q.lower() in {"exit", "quit"}:
                break
            if q.lower() == "reset":
                pipeline.reset_history()
                print("(history cleared)\n")
                continue
            _print_result(pipeline.ask(q))
        return 0

    if not args.question:
        parser.error("Provide a question or use --interactive.")

    _print_result(pipeline.ask(args.question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
