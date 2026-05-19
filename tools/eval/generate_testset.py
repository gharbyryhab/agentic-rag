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


# ─── Multi-chunk prompt (NEW for strategy="multi") ─────────────────────────────

GENERATE_QA_MULTI_PROMPT = """\
You are creating a high-quality evaluation Q/A pair for a RAG system about \
data science, machine learning, and AI.

Given the {n_passages} passages below, write ONE technical question whose \
answer REQUIRES synthesizing information from MULTIPLE passages (not just one), \
and the corresponding ground-truth answer (2-4 sentences).

Return ONLY a JSON object on a single line :
{{"question": "...", "ground_truth": "..."}}

Rules :
- The question must be self-contained (no "this passage" or "passage 1" references).
- The answer should require AT LEAST 2 of the provided passages.
- The question should test understanding of relationships or combined knowledge.
- Skip if no coherent multi-passage question can be formed by returning {{"skip": true}}.

Passages :
---
{passages}
---

Output (JSON only) :"""


def generate_multi(n: int, store: ChromaStore, llm: GeminiClient) -> list[dict]:
    """Sample N chunks together and generate a multi-hop Q/A that requires them all."""
    cfg = get_settings().evaluation.testset_gen
    k = cfg.multi_chunks_per_qa
    factor = cfg.sample_factor
    total = store.count()
    if total == 0:
        raise RuntimeError("Chroma collection is empty. Build the index first.")

    sample_n = min(n * k * factor, total)
    log.info(
        f"Sampling {sample_n} chunks (target {n} Q/A × {k} chunks each, factor={factor}) "
        f"from {total} total."
    )

    all_chunks = store.collection.get(
        limit=sample_n,
        include=["documents", "metadatas"],
    )
    pool = list(zip(all_chunks["ids"], all_chunks["documents"], all_chunks["metadatas"]))
    random.shuffle(pool)

    qas: list[dict] = []
    i = 0
    while len(qas) < n and i + k <= len(pool):
        batch = pool[i:i + k]
        i += k

        # Skip if any chunk too short
        if any(len(c[1]) < 200 for c in batch):
            continue

        passages_text = "\n\n---\n\n".join(
            f"[PASSAGE {j+1}]\n{c[1][:1500]}" for j, c in enumerate(batch)
        )
        try:
            response = llm.generate(GENERATE_QA_MULTI_PROMPT.format(
                n_passages=k, passages=passages_text
            ))
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
                "contexts": [c[1] for c in batch],   # N contexts, not 1
                "metadata": {
                    "chunk_ids": [c[0] for c in batch],
                    "book_titles": list({(c[2] or {}).get("book_title", "") for c in batch}),
                    "categories": list({(c[2] or {}).get("category", "") for c in batch}),
                    "n_chunks": k,
                },
            }
        )
        if len(qas) % 5 == 0:
            log.info(f"Generated {len(qas)}/{n}")
    return qas


def generate_ragas(n: int, store: ChromaStore) -> list[dict]:
    """Use Ragas 0.4.x TestsetGenerator (modern API).

    Uses LOCAL BGE embeddings to avoid Google Cloud quota / 404 errors.
    """
    try:
        from langchain_core.documents import Document
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_huggingface import HuggingFaceEmbeddings
        from ragas import RunConfig
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.testset import TestsetGenerator
    except ImportError as e:
        raise ImportError(
            "`pip install ragas>=0.4 datasets langchain-huggingface langchain-google-genai` required."
        ) from e

    cfg = get_settings()
    total = store.count()
    # Sub-sample size : Ragas needs enough docs to extract a knowledge graph,
    # but loading ALL 69k chunks would (a) explode SQLite's variable limit and
    # (b) make the knowledge-graph extraction extremely slow.
    target = min(total, max(n * 3, 50))
    log.info(f"Target {target} chunks via stratified sampling over full corpus ({total} total)…")

    # ─── Stratified proportional sampling with minimum floor ─────────────────
    # Stratégie : chaque livre contribue proportionnellement à sa taille,
    # avec un minimum garanti de 1 chunk pour ne jamais exclure un livre.
    # Contrairement à la pagination consécutive, cela garantit que les 150
    # chunks couvrent TOUS les livres du corpus.

    # Étape 1 — Charger tous les ids + métadonnées (pas les vecteurs → léger)
    BATCH = 5000
    all_ids: list[str] = []
    all_docs: list[str] = []
    all_metas: list[dict] = []
    for offset in range(0, total, BATCH):
        batch = store.collection.get(
            limit=min(BATCH, total - offset),
            offset=offset,
            include=["documents", "metadatas"],
        )
        all_ids.extend(batch["ids"])
        all_docs.extend(batch["documents"])
        all_metas.extend(batch["metadatas"] or [{}] * len(batch["ids"]))

    # Étape 2 — Grouper par book_title
    from collections import defaultdict
    book_index: dict[str, list[int]] = defaultdict(list)
    for i, meta in enumerate(all_metas):
        title = (meta or {}).get("book_title", "__unknown__") or "__unknown__"
        book_index[title].append(i)

    n_books = len(book_index)
    log.info(f"Corpus contains {n_books} distinct books.")

    # Étape 3 — Quota proportionnel avec minimum = 1 par livre
    raw_quotas: dict[str, float] = {
        title: target * (len(idxs) / total)
        for title, idxs in book_index.items()
    }
    # Appliquer le floor à 1
    floored: dict[str, int] = {t: max(1, round(q)) for t, q in raw_quotas.items()}

    # Étape 4 — Ajuster si la somme dépasse target
    total_allocated = sum(floored.values())
    if total_allocated > target:
        # Réduire les gros livres en priorité
        excess = total_allocated - target
        sorted_books = sorted(floored.keys(), key=lambda t: floored[t], reverse=True)
        for title in sorted_books:
            if excess == 0:
                break
            reducible = floored[title] - 1  # jamais descendre sous 1
            cut = min(reducible, excess)
            floored[title] -= cut
            excess -= cut

    # Étape 5 — Sélection aléatoire dans chaque livre
    documents: list = []
    for title, idxs in book_index.items():
        quota = floored[title]
        chosen = random.sample(idxs, min(quota, len(idxs)))
        for i in chosen:
            documents.append(Document(page_content=all_docs[i], metadata=all_metas[i] or {}))

    random.shuffle(documents)
    log.info(
        f"Stratified sample: {len(documents)} chunks from {n_books} books "
        f"(min 1 per book, proportional allocation)."
    )

    # ── Synthesizer LLM : configurable (groq or gemini), distinct du juge ─────
    # Principe : générateur et juge doivent être différents pour éviter le
    # biais "le prof corrige ses propres examens".
    # Recommandé : groq + openai/gpt-oss-120b (excellent JSON, fast).
    synth_cfg = cfg.evaluation.synthesizer
    log.info(
        f"Building Ragas TestsetGenerator "
        f"(synthesizer={synth_cfg.provider}/{synth_cfg.model}, "
        f"embeddings={cfg.embeddings.model_name})…"
    )

    if synth_cfg.provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as e:
            raise ImportError(
                "`pip install langchain-groq` required for groq synthesizer."
            ) from e
        if not cfg.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Set it in .env. "
                "Get a free key at https://console.groq.com/keys"
            )
        synth_llm_raw = ChatGroq(
            model=synth_cfg.model,
            api_key=cfg.groq_api_key,
            temperature=0,
            max_tokens=1024,
            timeout=120,
        )
    else:   # gemini fallback
        synth_llm_raw = ChatGoogleGenerativeAI(
            model=synth_cfg.model,
            google_api_key=cfg.gemini_api_key,
            temperature=0,
            max_output_tokens=1024,
            timeout=120,
        )
    generator_llm = LangchainLLMWrapper(synth_llm_raw)

    embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(
        model_name=cfg.embeddings.model_name,
        model_kwargs={"device": cfg.embeddings.device},
        encode_kwargs={"normalize_embeddings": cfg.embeddings.normalize},
    ))

    # max_workers calculated from RPM : we want to stay below the limit with margin
    # ex: 30 RPM = 1 call every 2s; 4 workers × 1 call / 8s = 30 RPM exactly
    max_workers = max(1, min(4, synth_cfg.rpm // 8))
    run_config = RunConfig(
        timeout=120,
        max_retries=3,
        max_wait=60,
        max_workers=max_workers,
    )
    log.info(f"RunConfig: max_workers={max_workers} (synthesizer rpm={synth_cfg.rpm})")

    generator = TestsetGenerator(llm=generator_llm, embedding_model=embeddings)
    log.info(f"Generating {n} Q/A with Ragas (this can take a while)…")
    dataset = generator.generate_with_langchain_docs(
        documents, testset_size=n, run_config=run_config,
    )
    df = dataset.to_pandas()
    log.info(f"Ragas returned {len(df)} rows, columns: {list(df.columns)}")

    qas: list[dict] = []
    for _, row in df.iterrows():
        # Ragas 0.4 uses 'user_input' / 'reference' / 'reference_contexts'
        # Fallback to older names for compatibility
        q = row.get("user_input") or row.get("question", "") or ""
        gt = row.get("reference") or row.get("ground_truth", "") or ""
        ctxs = row.get("reference_contexts") or row.get("contexts", []) or []
        if not q or not gt:
            continue
        qas.append(
            {
                "question": str(q),
                "ground_truth": str(gt),
                "contexts": [str(c) for c in (ctxs if isinstance(ctxs, list) else [ctxs])],
                "metadata": {
                    "synthesizer": str(row.get("synthesizer_name", "ragas")),
                },
            }
        )
    return qas


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a golden Q/A dataset.")
    parser.add_argument("--size", type=int, default=None, help="Number of Q/A pairs.")
    parser.add_argument(
        "--strategy",
        choices=["simple", "multi", "ragas"],
        default="simple",
        help="`simple` (1 chunk/QA, fast), `multi` (N chunks/QA from config, "
             "good for multi-hop), `ragas` (rich Q types via Ragas TestsetGenerator).",
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
    elif args.strategy == "multi":
        llm = GeminiClient()
        qas = generate_multi(n, store, llm)
    else:  # ragas
        qas = generate_ragas(n, store)

    # ─── Archive permanente ──────────────────────────────────────────
    # Tout nouveau testset est aussi sauvegardé dans results/eval/testsets/
    # avec un nom unique (strategy + timestamp + size) pour ne JAMAIS
    # écraser un testset précédent. Permet de comparer plusieurs runs.
    from datetime import datetime as _dt
    archive_dir = output.parent / "testsets"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"testset_{args.strategy}_{timestamp}_{len(qas)}q.json"
    archive_path = archive_dir / archive_name

    with archive_path.open("w", encoding="utf-8") as f:
        json.dump(qas, f, ensure_ascii=False, indent=2)
    log.info(f"Archived {len(qas)} Q/A pairs to {archive_path}")

    # ─── Pointeur "current" (utilisé par défaut par run_ragas) ──────
    with output.open("w", encoding="utf-8") as f:
        json.dump(qas, f, ensure_ascii=False, indent=2)
    log.info(f"Current testset → {output} (= copy of {archive_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())