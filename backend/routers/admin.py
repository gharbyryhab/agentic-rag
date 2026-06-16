"""Admin-only routes: user list, system status, settings, enhanced metrics."""
from __future__ import annotations

import math
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import require_admin
from backend.database import get_db
from backend import runtime_settings
from backend.models import AppSetting, Feedback, Message, RequestLog, Session, User
from backend.schemas import (
    AppSettingOut, SettingsPatch, SettingsOut, SystemStatus, UserActivity,
)

router = APIRouter(prefix="/admin", tags=["admin"])

_START_TIME = time.monotonic()


def _since(days: int | None) -> datetime | None:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _date_str(dt) -> str:
    if isinstance(dt, str):
        return dt[:10]
    return dt.strftime("%Y-%m-%d")


def _hour_str(dt) -> str:
    if isinstance(dt, str):
        return dt[:13]
    return dt.strftime("%Y-%m-%dT%H")


def _percentile(vals: list[float], pct: int) -> float | None:
    if not vals:
        return None
    idx = max(0, min(math.ceil(len(vals) * pct / 100) - 1, len(vals) - 1))
    return round(sorted(vals)[idx], 3)


# ─────────────────────────────────────────────
# User activity list
# ─────────────────────────────────────────────

@router.get("/users", response_model=list[UserActivity])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()

    # Per-user session count
    sess_counts = dict(
        (await db.execute(
            select(Session.user_id, func.count(Session.id))
            .where(Session.user_id.isnot(None))
            .group_by(Session.user_id)
        )).all()
    )

    # Per-user question count (user messages)
    q_counts = dict(
        (await db.execute(
            select(Session.user_id, func.count(Message.id))
            .join(Message, Message.session_id == Session.id)
            .where(Session.user_id.isnot(None), Message.role == "user")
            .group_by(Session.user_id)
        )).all()
    )

    # Last active = most recent session updated_at per user
    last_active = dict(
        (await db.execute(
            select(Session.user_id, func.max(Session.updated_at))
            .where(Session.user_id.isnot(None))
            .group_by(Session.user_id)
        )).all()
    )

    return [
        UserActivity(
            id=u.id,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            total_sessions=sess_counts.get(u.id, 0),
            total_questions=q_counts.get(u.id, 0),
            last_active=last_active.get(u.id),
        )
        for u in users
    ]


# ─────────────────────────────────────────────
# System status
# ─────────────────────────────────────────────

@router.get("/system-status", response_model=SystemStatus)
async def system_status(
    _admin: User = Depends(require_admin),
):
    pipeline_healthy = False
    chromadb_size = 0

    try:
        from backend.routers.chat import _get_pipeline
        pipeline = _get_pipeline()
        pipeline_healthy = pipeline is not None
    except Exception:
        pass

    try:
        from backend.routers.chat import _get_pipeline
        pipeline = _get_pipeline()
        if pipeline and hasattr(pipeline, "retriever"):
            ret = pipeline.retriever
            if hasattr(ret, "vector_store") and hasattr(ret.vector_store, "_collection"):
                chromadb_size = ret.vector_store._collection.count()
            elif hasattr(ret, "chroma") and hasattr(ret.chroma, "_collection"):
                chromadb_size = ret.chroma._collection.count()
    except Exception:
        pass

    from backend.database import DATABASE_URL
    db_path = DATABASE_URL.split("///")[-1] if ":///" in DATABASE_URL else DATABASE_URL

    return SystemStatus(
        pipeline_healthy=pipeline_healthy,
        model_name=runtime_settings.get("model_name"),
        chromadb_size=chromadb_size,
        db_path=db_path,
        uptime_s=round(time.monotonic() - _START_TIME, 1),
    )


# ─────────────────────────────────────────────
# Hourly queries (temporal chart)
# ─────────────────────────────────────────────

@router.get("/hourly-queries")
async def hourly_queries(
    days: int | None = Query(7, ge=1, le=90),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)
    q = select(RequestLog.created_at)
    if since:
        q = q.where(RequestLog.created_at >= since)

    rows = (await db.execute(q)).scalars().all()
    by_hour: dict[str, int] = defaultdict(int)
    for dt in rows:
        by_hour[_hour_str(dt)] += 1

    return [{"hour": h, "count": c} for h, c in sorted(by_hour.items())]


# ─────────────────────────────────────────────
# Daily latency percentiles
# ─────────────────────────────────────────────

@router.get("/latency-daily")
async def latency_daily(
    days: int | None = Query(30, ge=1, le=365),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)
    q = select(RequestLog.created_at, RequestLog.latency_s).where(
        RequestLog.latency_s.isnot(None)
    )
    if since:
        q = q.where(RequestLog.created_at >= since)

    rows = (await db.execute(q)).all()
    by_day: dict[str, list[float]] = defaultdict(list)
    for dt, lat in rows:
        by_day[_date_str(dt)].append(lat)

    return [
        {
            "date": day,
            "p50": _percentile(vals, 50),
            "p95": _percentile(vals, 95),
            "count": len(vals),
        }
        for day, vals in sorted(by_day.items())
    ]


# ─────────────────────────────────────────────
# Settings — GET / PATCH
# ─────────────────────────────────────────────

@router.get("/settings", response_model=SettingsOut)
async def get_settings(
    _admin: User = Depends(require_admin),
):
    s = runtime_settings.get_all()
    return SettingsOut(
        model_name=s["model_name"],
        temperature=float(s["temperature"]),
        top_k=int(s["top_k"]),
        max_sources=int(s["max_sources"]),
    )


@router.patch("/settings", response_model=SettingsOut)
async def patch_settings(
    body: SettingsPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    updates: dict[str, str] = {}
    if body.model_name is not None:
        updates["model_name"] = body.model_name
    if body.temperature is not None:
        updates["temperature"] = str(body.temperature)
    if body.top_k is not None:
        updates["top_k"] = str(body.top_k)
    if body.max_sources is not None:
        updates["max_sources"] = str(body.max_sources)

    # Upsert to DB
    for key, value in updates.items():
        row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalar_one_or_none()
        if row:
            row.value = value
            row.updated_by = admin.id
        else:
            db.add(AppSetting(key=key, value=value, updated_by=admin.id))

    await db.commit()

    # Hot-reload in memory
    runtime_settings.set_many(updates)

    s = runtime_settings.get_all()
    return SettingsOut(
        model_name=s["model_name"],
        temperature=float(s["temperature"]),
        top_k=int(s["top_k"]),
        max_sources=int(s["max_sources"]),
    )
