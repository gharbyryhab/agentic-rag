"""Gemini wrapper exposed both as a custom interface and a LangChain chat model."""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import get_settings
from src.llm.base import LLM
from src.utils import get_logger

log = get_logger(__name__)


class GeminiClient(LLM):
    """
    Thin wrapper over `ChatGoogleGenerativeAI` (LangChain).

    Exposes a simple `.generate()` / `.chat()` API for direct usage,
    plus `.as_langchain()` to get the underlying model for LangGraph nodes.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        if not cfg.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is missing. Copy .env.example to .env and fill it in."
            )

        self._cfg = cfg.llm
        self._model = ChatGoogleGenerativeAI(
            model=self._cfg.model_name,
            google_api_key=cfg.gemini_api_key,
            temperature=self._cfg.temperature,
            max_output_tokens=self._cfg.max_output_tokens,
            top_p=self._cfg.top_p,
            convert_system_message_to_human=False,
        )
        log.info(f"Gemini client ready: {self._cfg.model_name}")

    # ---------- High-level API ----------
    def generate(self, prompt: str, system: str | None = None, **kwargs: Any) -> str:
        msgs: list[BaseMessage] = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))
        result: AIMessage = self._model.invoke(msgs, **kwargs)
        return result.content if isinstance(result.content, str) else str(result.content)

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        msgs: list[BaseMessage] = []
        for m in messages:
            role, content = m["role"], m["content"]
            if role == "system":
                msgs.append(SystemMessage(content=content))
            elif role == "user":
                msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))
        result: AIMessage = self._model.invoke(msgs, **kwargs)
        return result.content if isinstance(result.content, str) else str(result.content)

    def as_langchain(self) -> ChatGoogleGenerativeAI:
        return self._model
