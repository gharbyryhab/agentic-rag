"""Conversation memory — kept simple : last-N turns sliding window."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Turn:
    role: str       # "user" | "assistant"
    content: str


class ConversationMemory:
    """In-memory chat history. Replace with Redis/DB for multi-session usage."""

    def __init__(self, max_turns: int = 10) -> None:
        self._turns: deque[Turn] = deque(maxlen=max_turns * 2)

    def add_user(self, content: str) -> None:
        self._turns.append(Turn("user", content))

    def add_assistant(self, content: str) -> None:
        self._turns.append(Turn("assistant", content))

    def history(self) -> list[dict[str, str]]:
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def as_text(self) -> str:
        return "\n".join(f"{t.role.upper()}: {t.content}" for t in self._turns)

    def clear(self) -> None:
        self._turns.clear()
