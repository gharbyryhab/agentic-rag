"""Interactive chat loop for testing conversational memory across CRAG and ReAct turns.

Usage:
    python -m scripts.chat
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import QueryPipeline  # noqa: E402


def _print_result(result: dict) -> None:
    route = result.get("route", "")
    print(f"\n[{route}] {result.get('answer', '')}")

    sources = result.get("sources") or []
    if sources:
        print(f"\nSources ({len(sources)}):")
        for s in sources:
            label = s.get("book_title") or s.get("source") or s.get("id") or "?"
            try:
                label = Path(label).name
            except Exception:  # noqa: BLE001
                pass
            page = s.get("page") or ""
            page_str = f", p.{page}" if page else ""
            score = s.get("score", 0.0)
            try:
                score_str = f"{float(score):.3f}"
            except Exception:  # noqa: BLE001
                score_str = "?"
            print(f"  [{score_str}] {label}{page_str}")


def main() -> None:
    pipeline = QueryPipeline()
    print("\nChat ready. Type 'exit' to quit, 'reset' to clear memory.\n")

    while True:
        try:
            question = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        if question.lower() == "reset":
            pipeline.reset_history()
            print("(memory cleared)\n")
            continue

        _print_result(pipeline.ask(question))
        print()


if __name__ == "__main__":
    main()
