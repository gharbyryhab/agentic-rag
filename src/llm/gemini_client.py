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
            # Hard cap per-request: avoids the script hanging indefinitely
            # when the Gemini endpoint stalls on a long prompt.
            timeout=self._cfg.timeout,
            # Retry transient errors (timeouts, 5xx, network blips) a few times.
            max_retries=self._cfg.max_retries,
        )
        log.info(
            f"Gemini client ready: {self._cfg.model_name} "
            f"(timeout={self._cfg.timeout}s, max_retries={self._cfg.max_retries})"
        )

    def _is_gemma3(self) -> bool:
        return "gemma-3" in self._cfg.model_name

    # ── NOUVELLE MÉTHODE CENTRALE ──────────────────────────────────────────
    def _extract_text(self, result: AIMessage) -> str:
        """
        Extrait proprement le texte d'une réponse LLM quel que soit le modèle.

        Cas 1 — gemma-3-* → result.content est une str directe
            "Le overfitting se produit..."
            → retourne tel quel

        Cas 2 — gemma-4-*, gemini-flash-lite → result.content est une liste de blocs :
            [{'type': 'thinking', 'thinking': '...'}, {'type': 'text', 'text': '...'}]
            → extrait uniquement le bloc type='text'

        Cas 3 — autres modèles → result.content est une str
            → retourne tel quel
        """
        content = result.content

        # Cas 1 et 3 : string directe → retourner tel quel
        if isinstance(content, str):
            return content

        # Cas 2 : liste de blocs → extraire uniquement les blocs 'text'
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    # 'thinking' → ignoré volontairement
                elif isinstance(block, str):
                    text_parts.append(block)
            result_text = "\n".join(text_parts).strip()
            if result_text:
                return result_text
            # Si aucun bloc text trouvé → fallback str()
            log.warning(f"No 'text' block found in response, blocks: {[b.get('type') for b in content if isinstance(b, dict)]}")
            return str(content)

        # Fallback ultime
        return str(content)

    # ──────────────────────────────────────────────────────────────────────

    def generate(self, prompt: str, system: str | None = None, **kwargs) -> str:
        msgs: list[BaseMessage] = []
        if system:
            if self._is_gemma3():
                # Gemma 3 ne supporte pas SystemMessage → fusionner dans le prompt
                prompt = f"{system}\n\n{prompt}"
            else:
                msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))
        result: AIMessage = self._model.invoke(msgs, **kwargs)
        return self._extract_text(result)   # ← remplace l'ancien str(result.content)

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        msgs: list[BaseMessage] = []

        # Extraire le system s'il existe
        system_content: str | None = None
        for m in messages:
            if m["role"] == "system":
                system_content = m["content"]
                break

        for m in messages:
            role, content = m["role"], m["content"]
            if role == "system":
                if self._is_gemma3():
                    continue  # géré ci-dessous sur le 1er HumanMessage
                else:
                    msgs.append(SystemMessage(content=content))
            elif role == "user":
                if self._is_gemma3() and system_content and not msgs:
                    # Fusionner system dans le 1er message utilisateur
                    msgs.append(HumanMessage(content=f"{system_content}\n\n{content}"))
                    system_content = None
                else:
                    msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))

        result: AIMessage = self._model.invoke(msgs, **kwargs)
        return self._extract_text(result)   # ← remplace l'ancien str(result.content)

    def as_langchain(self) -> ChatGoogleGenerativeAI:
        return self._model