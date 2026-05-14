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

    route = result.get("route", "")
    print("\n" + "=" * 70)
    print("RÉPONSE" + (f"  (route: {route})" if route else ""))
    print("=" * 70)
    print(result.get("answer", ""))

    sources = result.get("sources") or []
    if sources:
        print("\n" + "-" * 70)
        print(f"SOURCES ({len(sources)})")
        print("-" * 70)
        for i, s in enumerate(sources, 1):
            # Pick the best display label available
            label = s.get("book_title") or s.get("source") or s.get("id") or "?"
            try:
                label = Path(label).name if label else "?"
            except Exception:  # noqa: BLE001
                pass
            page = s.get("page") or ""
            page_str = f", p.{page}" if page else ""
            score = s.get("score", 0.0)
            try:
                score_str = f"{float(score):.3f}"
            except Exception:  # noqa: BLE001
                score_str = "?"
            snippet = s.get("snippet") or s.get("tool_output_excerpt") or ""
            print(f"{i}. [{score_str}] {label}{page_str}")
            print(f"   {snippet[:120]}...")
    if result.get("tool_calls") is not None:
        print(f"\n(tool calls : {result['tool_calls']})")
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
