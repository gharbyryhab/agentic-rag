"""SQLAlchemy ORM models (SQLite)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user", nullable=False)  # "admin" | "user"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    sessions: Mapped[list[Session]] = relationship("Session", back_populates="user")


# ─────────────────────────────────────────────
# App Settings (runtime overrides, admin only)
# ─────────────────────────────────────────────

class AppSetting(Base):
    """Key-value store for runtime-configurable settings."""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


# ─────────────────────────────────────────────
# Sessions & Messages
# ─────────────────────────────────────────────

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, default="New conversation")
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    user: Mapped[User | None] = relationship("User", back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )
    logs: Mapped[list[RequestLog]] = relationship(
        "RequestLog", back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # Assistant-only metadata
    route: Mapped[str | None] = mapped_column(String, nullable=True)       # "simple" | "agent"
    latency_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)       # list of source dicts

    session: Mapped[Session] = relationship("Session", back_populates="messages")
    feedback: Mapped[Feedback | None] = relationship(
        "Feedback", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────
# Feedback
# ─────────────────────────────────────────────

class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False, unique=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)   # +1 (👍) | -1 (👎)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    message: Mapped[Message] = relationship("Message", back_populates="feedback")


# ─────────────────────────────────────────────
# Request logs
# ─────────────────────────────────────────────

class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_sources: Mapped[int | None] = mapped_column(Integer, nullable=True)
    online_judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    session: Mapped[Session | None] = relationship("Session", back_populates="logs")


# ─────────────────────────────────────────────
# Evaluation runs & metrics
# ─────────────────────────────────────────────

class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tag: Mapped[str] = mapped_column(String, nullable=False)
    chunking_strategy: Mapped[str | None] = mapped_column(String, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    metrics: Mapped[list[EvalMetric]] = relationship(
        "EvalMetric", back_populates="run", cascade="all, delete-orphan"
    )


class EvalMetric(Base):
    __tablename__ = "eval_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped[EvalRun] = relationship("EvalRun", back_populates="metrics")
