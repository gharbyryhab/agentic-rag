"""LangChain tools exposed to the ReAct agent.

Each `make_*` is a closure that captures shared dependencies (retriever,
metadata store) and returns a `@tool`-decorated function with a clean
docstring used by the LLM as the tool description.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from src.ingestion import get_book_metadata_store
from src.retrieval import Retriever
from src.utils import get_logger
from src.vector_store.base import SearchResult

log = get_logger(__name__)


# ---------- Formatting helpers ----------

def _format_results(results: list[SearchResult], max_chars: int = 800) -> str:
    if not results:
        return "No relevant passages found."
    blocks = []
    for r in results:
        book = r.metadata.get("book_title") or r.metadata.get("source", "unknown")
        author = r.metadata.get("author", "")
        page = r.metadata.get("page", "")
        header = f"[{book}" + (f" — {author}" if author else "") + (f", p.{page}" if page else "") + "]"
        snippet = r.text[:max_chars] + ("…" if len(r.text) > max_chars else "")
        blocks.append(f"{header}\n{snippet}")
    return "\n\n---\n\n".join(blocks)


# ---------- Factories ----------

def make_search_knowledge_base(retriever: Retriever):
    @tool("search_knowledge_base")
    def search_knowledge_base(query: str) -> str:
        """Search the full data-science / ML / AI knowledge base by semantic + lexical similarity.

        Use for general questions when no specific filter is needed.
        Args:
            query: A precise, self-contained search query in English (the corpus is English-heavy).
        Returns:
            Top relevant passages with their source book / author / page.
        """
        results = retriever.retrieve(query)
        return _format_results(results)

    return search_knowledge_base


def make_search_by_category(retriever: Retriever):
    @tool("search_by_category")
    def search_by_category(query: str, category: str) -> str:
        """Search filtered by a thematic category.

        Use when the question is clearly about a specific area (e.g. deep learning,
        NLP, mathematics).

        Args:
            query: A self-contained search query.
            category: One of [deep_learning, NLP, mathematics_ml, generative_AI,
                data_science_appliquee_python, business_IA, fondements_ML_theorie_algorithmes,
                feature_engineering_modelisation, sujets_complementaires,
                IA_generale_introductions, specifique_R, superficiel_grand_public].
        """
        try:
            results = retriever.retrieve(query, where={"category": category})
        except Exception as e:  # noqa: BLE001
            log.warning(f"search_by_category failed ({category}): {e}")
            return f"Category filter '{category}' invalid or empty. Fall back to search_knowledge_base."
        return _format_results(results)

    return search_by_category


def make_search_by_level(retriever: Retriever):
    @tool("search_by_level")
    def search_by_level(query: str, level: str) -> str:
        """Search filtered by difficulty level.

        Args:
            query: A self-contained search query.
            level: One of [beginner, intermediate, advanced, expert].
        """
        level = level.lower().strip()
        if level not in {"beginner", "intermediate", "advanced", "expert"}:
            return f"Invalid level '{level}'. Use beginner | intermediate | advanced | expert."
        results = retriever.retrieve(query, where={"level": level})
        return _format_results(results)

    return search_by_level


def make_get_book_info():
    book_meta = get_book_metadata_store()

    @tool("get_book_info")
    def get_book_info(title_query: str) -> str:
        """Get rich metadata about a specific book by matching its title.

        Returns description, target audience, key chapters, level, domain.
        Use when the user asks about a specific book.

        Args:
            title_query: Part of the book title (case-insensitive).
        """
        # Brute-force substring match on the internal lookup
        q = title_query.lower().strip()
        for filename, meta in book_meta._by_filename.items():  # noqa: SLF001
            title = (meta.get("title") or "").lower()
            if q in title or q in filename.lower():
                lines = [
                    f"Title       : {meta.get('title', filename)}",
                    f"Author      : {meta.get('author', '?')}",
                    f"Domain      : {meta.get('detected_domain', meta.get('main_domain', '?'))}",
                    f"Level       : {meta.get('level', '?')}",
                    f"Language    : {meta.get('language', '?')}",
                    f"Audience    : {meta.get('target_audience', '?')}",
                    f"Description : {meta.get('description', '?')}",
                    "Key chapters:",
                ]
                for ch in (meta.get("key_chapters") or [])[:8]:
                    lines.append(f"  - {ch}")
                return "\n".join(lines)
        return f"No book matching '{title_query}' in the knowledge base."

    return get_book_info


def make_compare_concepts(retriever: Retriever):
    @tool("compare_concepts")
    def compare_concepts(concept_a: str, concept_b: str) -> str:
        """Retrieve passages about TWO concepts so they can be compared side by side.

        Args:
            concept_a: First concept (e.g. "Random Forest").
            concept_b: Second concept (e.g. "Gradient Boosting").
        """
        results_a = retriever.retrieve(concept_a, top_k=3)
        results_b = retriever.retrieve(concept_b, top_k=3)
        return (
            f"=== Concept A : {concept_a} ===\n{_format_results(results_a)}\n\n"
            f"=== Concept B : {concept_b} ===\n{_format_results(results_b)}"
        )

    return compare_concepts


# ---------- Public API ----------

def build_all_tools(retriever: Retriever) -> list[Any]:
    """Return the full tool palette as a list of LangChain `@tool` objects."""
    return [
        make_search_knowledge_base(retriever),
        make_search_by_category(retriever),
        make_search_by_level(retriever),
        make_get_book_info(),
        make_compare_concepts(retriever),
    ]
