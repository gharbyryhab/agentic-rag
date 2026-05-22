"""Pydantic schemas for request/response validation."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None   # None → create new session


class SourceOut(BaseModel):
    source: str = ""
    book_title: str = ""
    page: str | int = ""
    score: float = 0.0
    snippet: str = ""

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    route: str
    latency_s: float
    sources: list[SourceOut]


# ─────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    route: str | None = None
    latency_s: float | None = None
    sources: list[dict] | None = None
    feedback_rating: int | None = None

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    messages: list[MessageOut] = []


# ─────────────────────────────────────────────
# Feedback
# ─────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    rating: int = Field(..., ge=-1, le=1)   # -1 or +1
    comment: str | None = None


class FeedbackOut(BaseModel):
    id: str
    message_id: str
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Metrics / Dashboard
# ─────────────────────────────────────────────

class EvalRunOut(BaseModel):
    id: str
    tag: str
    chunking_strategy: str | None
    sample_size: int | None
    created_at: datetime
    metrics: dict[str, float | None] = {}

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_sessions: int
    total_messages: int
    total_questions: int
    avg_latency_s: float | None
    route_distribution: dict[str, int]   # {"simple": 40, "agent": 12}
    thumbs_up: int
    thumbs_down: int
    last_eval: EvalRunOut | None = None
