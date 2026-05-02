"""LangChain tools the agent can call.

Currently exposes a single `knowledge_base_search` tool wrapping the retriever.
Add new @tool functions here (e.g. web search, calculator) as you grow.
"""
from __future__ import annotations

from langchain_core.tools import tool

from src.retrieval import Retriever


def make_kb_search_tool(retriever: Retriever):
    """Factory : binds the retriever instance into a LangChain tool."""

    @tool("knowledge_base_search")
    def knowledge_base_search(query: str) -> str:
        """Search the local data science / ML / AI knowledge base for relevant passages.
        Args:
            query: A precise, self-contained question or keyword phrase.
        Returns:
            Concatenated top passages with their source IDs.
        """
        results = retriever.retrieve(query)
        if not results:
            return "No relevant passages found."
        chunks = []
        for r in results:
            src = r.metadata.get("source", r.id)
            chunks.append(f"[source: {src}]\n{r.text}")
        return "\n\n---\n\n".join(chunks)

    return knowledge_base_search
