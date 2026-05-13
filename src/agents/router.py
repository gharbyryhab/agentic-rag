"""LLM-based query router : decides between simple CRAG path and ReAct agent path."""
from __future__ import annotations

from src.config import get_prompts, get_settings
from src.llm import LLM
from src.utils import get_logger

log = get_logger(__name__)


class QueryRouter:
    """One-shot LLM classifier returning 'simple' or 'agent'."""

    VALID = {"simple", "agent"}

    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self._cfg = get_settings().agent
        self._prompts = get_prompts()

    def route(self, question: str) -> str:
        if not self._cfg.enable_router:
            return self._cfg.router_default
        try:
            system = self._prompts["router_system"]
            verdict = self.llm.generate(question, system=system).strip().lower()
            # Normalize : take the first word
            verdict = verdict.split()[0] if verdict else ""
            verdict = verdict.strip(".,!?\"'")
            if verdict in self.VALID:
                log.debug(f"Router → {verdict}")
                return verdict
            log.warning(f"Router returned unexpected '{verdict}', falling back to default")
        except Exception as e:  # noqa: BLE001
            log.warning(f"Router LLM call failed: {e}")
        return self._cfg.router_default
