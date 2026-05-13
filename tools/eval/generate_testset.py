"""Generate a Golden Q/A dataset from the indexed corpus.

Two strategies :
  1. `ragas` — use Ragas' TestsetGenerator (synthetic multi-type questions)
  2. `simple` — sample chunks and ask Gemini to write a Q/A per chunk

The output is a JSON file at `results/eval/testset.json` with schema :
    [
      {
        "question": "...",
        "ground_truth": "...",
        "contexts": ["...", ...],
        "metadata": {"book_title": ..., "category": ..., ...}
      },
      ...
    ]

Usage :
    python -m tools.eval.generate_testset --size 50 --strategy simple
    python -m tools.eval.generate_testset --size 100 --strategy ragas
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.llm import GeminiClient  # noqa: E402
from src.utils import get_logger  # noqa: E402
from src.vector_store import ChromaStore  # noqa: E402

log = get_logger("generate_testset")


GENERATE_QA_PROMPT = """\
You are creating a high-quality evaluation Q/A pair for a RAG system about \
data science, machine learning, and AI.

Given the passage below, write ONE technical question that can be FULLY \
answered using only this passage, and the corresponding short ground-truth \
answer (1-3 sentences).

Return ONLY a JSON object on a single line :
{{"question": "...", "ground_truth": "..."}}

Rules :
- The question must be self-contained (no "this passage" references).
- The question should test understanding, not just keyword matching.
- Skip if the passage is too short, too generic, or just a heading.
- Skip by returning {{"skip": true}} if not suitable.

Passage :
---
{passage}
---

Output (JSON only) :"""


def _parse_qa(response: str) -> dict | None:
    """Extract JSON from LLM response, robust to code fences."""
    text = response.strip()
    if "```" in text:
        # Strip code fences
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def generate_simple(n: int, store: ChromaStore, llm: GeminiClient) -> list[dict]:
    """Sample n random chunks and ask Gemini to produce a Q/A for each."""
    total = store.count()
    if total == 0:
        raise RuntimeError("Chroma collection is empty. Build the index first.")

    sample_n = min(n * 3, total)  # over-sample to allow skips
    log.info(f"Sampling {sample_n} chunks (target {n}) from {total} total.")

    # Fetch a wide sample : Chroma doesn't have a true random API, so we
    # paginate offsets and shuffle.
    all_chunks = store.collection.get(
        limit=sample_n,
        include=["documents", "metadatas"],
    )
    ids = all_chunks["ids"]
    docs = all_chunks["documents"]
    metas = all_chunks["metadatas"]
    pool = list(zip(ids, docs, metas))
    random.shuffle(pool)

    qas: list[dict] = []
    for i, (chunk_id, text, meta) in enumerate(pool):
        if len(qas) >= n:
            break
        if len(text) < 200:  # skip too-short chunks
            continue
        try:
            response = llm.generate(GENERATE_QA_PROMPT.format(passage=text[:2500]))
        except Exception as e:  # noqa: BLE001
            log.warning(f"[{i}] LLM call failed : {e}")
            continue
        parsed = _parse_qa(response)
        if not parsed or parsed.get("skip"):
            continue
        if "question" not in parsed or "ground_truth" not in parsed:
            continue
        qas.append(
            {
                "question": parsed["question"],
                "ground_truth": parsed["ground_truth"],
                "contexts": [text],
                "metadata": {
                    "chunk_id": chunk_id,
                    "book_title": (meta or {}).get("book_title", ""),
                    "category": (meta or {}).get("category", ""),
                    "source": (meta or {}).get("source", ""),
                    "page": (meta or {}).get("page", ""),
                },
            }
        )
        if len(qas) % 5 == 0:
            log.info(f"Generated {len(qas)}/{n}")
    return qas


def generate_ragas(n: int, store: ChromaStore) -> list[dict]:
    """Use Ragas TestsetGenerator (heavier, multiple question types)."""
    try:
        from datasets import Dataset
        from langchain_core.documents import Document
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
            GoogleGenerativeAIEmbeddings,
        )
        from ragas.testset.generator import TestsetGenerator
        from ragas.testset.evolutions import multi_context, reasoning, simple
    except ImportError as e:
        raise ImportError("`pip install ragas datasets` required.") from e

    cfg = get_settings()
    log.info("Loading entire Chroma collection as Document corpus (may take a moment)…")
    all_chunks = store.collection.get(include=["documents", "metadatas"])
    documents = [
        Document(page_content=text, metadata=meta or {})
        for text, meta in zip(all_chunks["documents"], all_chunks["metadatas"])
    ]
    # Subsample for tractable generation
    random.shuffle(documents)
    documents = documents[: min(len(documents), n * 5)]

    generator_llm = ChatGoogleGenerativeAI(
        model=cfg.evaluation.judge_model,
        google_api_key=cfg.gemini_api_key,
        temperature=0,
    )
    critic_llm = ChatGoogleGenerativeAI(
        model=cfg.evaluation.judge_model,
        google_api_key=cfg.gemini_api_key,
        temperature=0,
    )
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=cfg.gemini_api_key,
    )

    generator = TestsetGenerator.from_langchain(
        generator_llm=generator_llm,
        critic_llm=critic_llm,
        embeddings=embeddings,
    )

    testset = generator.generate_with_langchain_docs(
        documents,
        test_size=n,
        distributions={simple: 0.5, reasoning: 0.3, multi_context: 0.2},
    )
    df = testset.to_pandas()

    qas: list[dict] = []
    for _, row in df.iterrows():
        qas.append(
            {
                "question": row.get("question", ""),
                "ground_truth": row.get("ground_truth", ""),
                "contexts": list(row.get("contexts", [])),
                "metadata": {"evolution_type": row.get("evolution_type", "simple")},
            }
        )
    return qas


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a golden Q/A dataset.")
    parser.add_argument("--size", type=int, default=None, help="Number of Q/A pairs.")
    parser.add_argument(
        "--strategy",
        choices=["simple", "ragas"],
        default="simple",
        help="`simple` is fast and cheap; `ragas` produces richer question types.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    cfg = get_settings()
    n = args.size or cfg.evaluation.testset_size

    store = ChromaStore()
    if store.count() == 0:
        log.error("Chroma collection is empty. Run `python -m scripts.build_index` first.")
        return 1

    output = cfg.absolute_path(cfg.evaluation.testset_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"Generating {n} Q/A pairs using strategy='{args.strategy}'")
    if args.strategy == "simple":
        llm = GeminiClient()
        qas = generate_simple(n, store, llm)
    else:
        qas = generate_ragas(n, store)

    with output.open("w", encoding="utf-8") as f:
        json.dump(qas, f, ensure_ascii=False, indent=2)
    log.info(f"Saved {len(qas)} Q/A pairs to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
