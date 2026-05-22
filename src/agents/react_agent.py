"""ReAct tool-using agent built on LangGraph's prebuilt `create_react_agent`.

The agent receives the user question, picks tools to call, and iterates
until it has enough context to answer. Hard-capped by `react.max_tool_calls`.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.agents.tools import build_all_tools
from src.config import get_prompts, get_settings
from src.llm import GeminiClient
from src.retrieval import Retriever
from src.utils import get_logger
from src.utils.io import extract_message_text

log = get_logger(__name__)


class ReActAgent:
    def __init__(self, retriever: Retriever, llm: GeminiClient) -> None:
        self.retriever = retriever
        self.llm = llm
        self._cfg = get_settings().agent
        self._prompts = get_prompts()
        self._tools = build_all_tools(retriever)
        # LangGraph prebuilt ReAct agent — binds tools to the chat model
        self._graph = create_react_agent(
            llm.as_langchain(),
            tools=self._tools,
        )

    def run(self, question: str, history: list[dict] | None = None) -> dict[str, Any]:
        messages: list = [SystemMessage(content=self._prompts["react_system"])]
        for turn in (history or []):
            if turn["role"] == "user":
                messages.append(HumanMessage(content=turn["content"]))
            elif turn["role"] == "assistant":
                messages.append(AIMessage(content=turn["content"]))
        messages.append(HumanMessage(content=question))

        max_calls = self._cfg.react.max_tool_calls
        timeout_s = self._cfg.react.timeout_s

        tool_call_count = 0
        final_answer = ""
        sources: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []

        try:
            for chunk in self._graph.stream(
                {"messages": messages},
                config={
                    "recursion_limit": max_calls * 4 + 5,
                    "timeout": timeout_s,
                },
            ):
                for node_name, payload in chunk.items():
                    msgs = payload.get("messages", []) if isinstance(payload, dict) else []
                    for m in msgs:
                        if hasattr(m, "tool_calls") and m.tool_calls:
                            tool_call_count += len(m.tool_calls)
                            for tc in m.tool_calls:
                                trace.append(
                                    {
                                        "node": node_name,
                                        "tool": tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "?"),
                                        "args": tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {}),
                                    }
                                )
                                if tool_call_count > max_calls:
                                    log.warning(f"Hit max_tool_calls={max_calls}, stopping early")
                                    break
                        if getattr(m, "type", None) == "tool":
                            tool_text = extract_message_text(getattr(m, "content", ""))
                            tool_name = getattr(m, "name", "tool")
                            sources.append(
                                {
                                    "source": f"<tool:{tool_name}>",
                                    "book_title": tool_name,
                                    "page": "",
                                    "score": 0.0,
                                    "snippet": tool_text,
                                }
                            )
                        if getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None):
                            final_answer = extract_message_text(m.content)
                if tool_call_count > max_calls:
                    break
        except TimeoutError:
            log.warning(f"ReAct graph timed out after {timeout_s}s")
            raise TimeoutError(f"ReAct graph timed out after {timeout_s}s")

        return {
            "answer": final_answer or "No answer produced.",
            "sources": sources,
            "contexts": [s.get("snippet", "") for s in sources if s.get("snippet")],
            "trace": trace,
            "tool_calls": tool_call_count,
        }
