"""GET /metrics — dashboard stats, eval runs, request logs."""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import EvalMetric, EvalRun, Feedback, Message, RequestLog, Session, User
from backend.schemas import DashboardStats, EvalRunOut

router = APIRouter(prefix="/metrics", tags=["metrics"])

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "results" / "eval"


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def _since(days: int | None) -> datetime | None:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _percentile(sorted_vals: list[float], pct: int) -> float | None:
    if not sorted_vals:
        return None
    idx = max(0, min(math.ceil(len(sorted_vals) * pct / 100) - 1, len(sorted_vals) - 1))
    return round(sorted_vals[idx], 2)


def _normalize(q: str) -> str:
    return re.sub(r"[^\w\s]", "", q.lower()).strip()[:200]


def _avg(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 2) if vals else None


def _date_str(dt) -> str:
    if isinstance(dt, str):
        return dt[:10]
    return dt.strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    days: int | None = Query(None, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)

    # Session count
    sess_q = select(func.count(Session.id))
    if since:
        sess_q = sess_q.where(Session.created_at >= since)
    total_sessions = (await db.execute(sess_q)).scalar() or 0

    # Message count
    msg_q = select(func.count(Message.id))
    if since:
        msg_q = msg_q.where(Message.created_at >= since)
    total_messages = (await db.execute(msg_q)).scalar() or 0

    # Question (user message) count
    q_q = select(func.count(Message.id)).where(Message.role == "user")
    if since:
        q_q = q_q.where(Message.created_at >= since)
    total_questions = (await db.execute(q_q)).scalar() or 0

    # Fetch all latency values for avg + percentile computation
    lat_q = select(RequestLog.latency_s).where(RequestLog.latency_s.isnot(None))
    if since:
        lat_q = lat_q.where(RequestLog.created_at >= since)
    lat_vals: list[float] = sorted((await db.execute(lat_q)).scalars().all())

    # Route distribution
    route_q = (
        select(RequestLog.route, func.count(RequestLog.id))
        .where(RequestLog.route.isnot(None))
        .group_by(RequestLog.route)
    )
    if since:
        route_q = route_q.where(RequestLog.created_at >= since)
    route_dist = {r: c for r, c in (await db.execute(route_q)).all()}

    # Feedback counts
    fb_up_q = select(func.count(Feedback.id)).where(Feedback.rating == 1)
    fb_dn_q = select(func.count(Feedback.id)).where(Feedback.rating == -1)
    if since:
        fb_up_q = fb_up_q.where(Feedback.created_at >= since)
        fb_dn_q = fb_dn_q.where(Feedback.created_at >= since)
    thumbs_up = (await db.execute(fb_up_q)).scalar() or 0
    thumbs_down = (await db.execute(fb_dn_q)).scalar() or 0

    # Last eval run — always all-time, not filtered by days
    last_eval_row = (
        await db.execute(
            select(EvalRun)
            .options(selectinload(EvalRun.metrics))
            .order_by(EvalRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_eval = _eval_run_to_out(last_eval_row) if last_eval_row else None

    return DashboardStats(
        total_sessions=total_sessions,
        total_messages=total_messages,
        total_questions=total_questions,
        avg_latency_s=_avg(lat_vals),
        latency_p50=_percentile(lat_vals, 50),
        latency_p95=_percentile(lat_vals, 95),
        latency_p99=_percentile(lat_vals, 99),
        route_distribution=route_dist,
        thumbs_up=thumbs_up,
        thumbs_down=thumbs_down,
        last_eval=last_eval,
    )


# ─────────────────────────────────────────────
# Eval runs
# ─────────────────────────────────────────────

@router.get("/eval", response_model=list[EvalRunOut])
async def list_eval_runs(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(EvalRun)
            .options(selectinload(EvalRun.metrics))
            .order_by(EvalRun.created_at.desc())
        )
    ).scalars().all()
    return [_eval_run_to_out(r) for r in rows]


@router.post("/eval/import", response_model=EvalRunOut, status_code=201)
async def import_eval_from_disk(tag: str, db: AsyncSession = Depends(get_db)):
    """
    Import a Ragas evaluation run from results/eval/<tag>/metrics.json into SQLite.
    Call this after running `python -m tools.eval.run_ragas --tag <tag>`.
    """
    candidates = sorted(EVAL_DIR.glob(f"{tag}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail=f"No eval dir found matching '{tag}' in {EVAL_DIR}")

    run_dir = candidates[0]
    metrics_file = run_dir / "metrics.json"
    if not metrics_file.exists():
        raise HTTPException(status_code=404, detail=f"metrics.json not found in {run_dir}")

    with metrics_file.open() as f:
        metrics_data: dict = json.load(f)

    config_file = run_dir / "config_snapshot.yaml"
    chunking = None
    sample_size = None
    if config_file.exists():
        import yaml
        with config_file.open() as f:
            snap = yaml.safe_load(f)
        meta = snap.get("_meta", {})
        chunking = meta.get("chunking_strategy")
        sample_size = meta.get("sample_size")

    run = EvalRun(tag=run_dir.name, chunking_strategy=chunking, sample_size=sample_size)
    db.add(run)
    await db.flush()

    for name, score in metrics_data.items():
        db.add(EvalMetric(run_id=run.id, metric_name=name, score=score if score == score else None))

    await db.commit()
    await db.refresh(run)
    run_with_metrics = (
        await db.execute(
            select(EvalRun).where(EvalRun.id == run.id).options(selectinload(EvalRun.metrics))
        )
    ).scalar_one()
    return _eval_run_to_out(run_with_metrics)


# ─────────────────────────────────────────────
# Request logs (for timeline charts)
# ─────────────────────────────────────────────

@router.get("/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    days: int | None = Query(None, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)

    count_q = select(func.count(RequestLog.id))
    rows_q = select(RequestLog).order_by(RequestLog.created_at.desc())
    if since:
        count_q = count_q.where(RequestLog.created_at >= since)
        rows_q = rows_q.where(RequestLog.created_at >= since)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    rows = (await db.execute(rows_q.offset(offset).limit(page_size))).scalars().all()

    items = [
        {
            "id": r.id,
            "question": r.question[:80],
            "route": r.route,
            "latency_s": r.latency_s,
            "n_sources": r.n_sources,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


# ─────────────────────────────────────────────
# Daily sessions & questions
# ─────────────────────────────────────────────

@router.get("/daily-sessions")
async def daily_sessions(
    days: int | None = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)

    sess_q = select(Session.created_at)
    req_q = select(RequestLog.created_at)
    if since:
        sess_q = sess_q.where(Session.created_at >= since)
        req_q = req_q.where(RequestLog.created_at >= since)

    sess_dts = (await db.execute(sess_q)).scalars().all()
    req_dts = (await db.execute(req_q)).scalars().all()

    sessions_by_date: dict[str, int] = defaultdict(int)
    for dt in sess_dts:
        sessions_by_date[_date_str(dt)] += 1

    questions_by_date: dict[str, int] = defaultdict(int)
    for dt in req_dts:
        questions_by_date[_date_str(dt)] += 1

    all_dates = sorted(set(sessions_by_date) | set(questions_by_date))
    return [
        {
            "date": date,
            "sessions": sessions_by_date.get(date, 0),
            "questions": questions_by_date.get(date, 0),
        }
        for date in all_dates
    ]


# ─────────────────────────────────────────────
# Daily feedback satisfaction trend
# ─────────────────────────────────────────────

@router.get("/feedback-trend")
async def feedback_trend(
    days: int | None = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)

    fb_q = select(Feedback.created_at, Feedback.rating).order_by(Feedback.created_at)
    if since:
        fb_q = fb_q.where(Feedback.created_at >= since)

    rows = (await db.execute(fb_q)).all()

    daily: dict[str, dict] = defaultdict(lambda: {"total": 0, "up": 0})
    for dt, rating in rows:
        d = _date_str(dt)
        daily[d]["total"] += 1
        if rating == 1:
            daily[d]["up"] += 1

    return [
        {
            "date": date,
            "rate": round(v["up"] / v["total"], 3),
            "total": v["total"],
        }
        for date, v in sorted(daily.items())
        if v["total"] > 0
    ]


# ─────────────────────────────────────────────
# Top questions
# ─────────────────────────────────────────────

@router.get("/top-questions")
async def top_questions(
    days: int | None = Query(None, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)

    q = select(RequestLog.question, RequestLog.latency_s)
    if since:
        q = q.where(RequestLog.created_at >= since)

    rows = (await db.execute(q)).all()

    groups: dict[str, list] = defaultdict(list)
    originals: dict[str, str] = {}

    for question, latency in rows:
        if not question:
            continue
        norm = _normalize(question)
        if not norm:
            continue
        if norm not in originals:
            originals[norm] = question
        groups[norm].append(latency)

    top = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)[:limit]

    return [
        {
            "question": originals[norm][:200],
            "count": len(latencies),
            "avg_latency": _avg([l for l in latencies if l is not None]),
        }
        for norm, latencies in top
    ]


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Per-user dashboard (filtered by current user)
# ─────────────────────────────────────────────

@router.get("/my-dashboard")
async def my_dashboard(
    days: int | None = Query(None, ge=1, le=3650),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns stats filtered to the current user's sessions only."""
    since = _since(days)

    # User's session IDs
    sess_q = select(Session.id, Session.created_at).where(Session.user_id == current_user.id)
    if since:
        sess_q = sess_q.where(Session.created_at >= since)
    user_sessions = (await db.execute(sess_q)).all()
    session_ids = [s[0] for s in user_sessions]

    total_sessions = len(session_ids)

    # Questions & latency from user's sessions
    total_questions = 0
    lat_vals: list[float] = []
    thumbs_up = 0
    thumbs_down = 0
    daily_questions: dict[str, int] = defaultdict(int)
    daily_sessions: dict[str, int] = defaultdict(int)

    for sid, created in user_sessions:
        daily_sessions[_date_str(created)] += 1

    if session_ids:
        # Questions count
        msgs = (await db.execute(
            select(Message.created_at, Message.latency_s, Message.role)
            .where(Message.session_id.in_(session_ids))
        )).all()
        for created, lat, role in msgs:
            if role == "user":
                total_questions += 1
                daily_questions[_date_str(created)] += 1
            if role == "assistant" and lat is not None:
                lat_vals.append(lat)

        # Feedback
        fb = (await db.execute(
            select(Feedback.rating, Feedback.created_at)
            .join(Message, Feedback.message_id == Message.id)
            .where(Message.session_id.in_(session_ids))
        )).all()
        for rating, _ in fb:
            if rating == 1:
                thumbs_up += 1
            elif rating == -1:
                thumbs_down += 1

    lat_vals_sorted = sorted(lat_vals)

    # Daily chart data
    all_dates = sorted(set(daily_sessions) | set(daily_questions))
    daily = [
        {
            "date": d,
            "sessions": daily_sessions.get(d, 0),
            "questions": daily_questions.get(d, 0),
        }
        for d in all_dates
    ]

    return {
        "total_sessions": total_sessions,
        "total_questions": total_questions,
        "avg_latency_s": _avg(lat_vals_sorted),
        "latency_p50": _percentile(lat_vals_sorted, 50),
        "latency_p95": _percentile(lat_vals_sorted, 95),
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "daily": daily,
    }


def _eval_run_to_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=run.id,
        tag=run.tag,
        chunking_strategy=run.chunking_strategy,
        sample_size=run.sample_size,
        created_at=run.created_at,
        metrics={m.metric_name: m.score for m in run.metrics},
    )
