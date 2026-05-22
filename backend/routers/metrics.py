"""GET /metrics — dashboard stats, eval runs, request logs."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import EvalMetric, EvalRun, Feedback, Message, RequestLog, Session
from backend.schemas import DashboardStats, EvalRunOut

router = APIRouter(prefix="/metrics", tags=["metrics"])

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "results" / "eval"


# ─────────────────────────────────────────────
# Dashboard stats
# ─────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: AsyncSession = Depends(get_db)):
    total_sessions = (await db.execute(select(func.count(Session.id)))).scalar() or 0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_questions = (
        await db.execute(select(func.count(Message.id)).where(Message.role == "user"))
    ).scalar() or 0

    avg_latency = (
        await db.execute(
            select(func.avg(RequestLog.latency_s)).where(RequestLog.latency_s.isnot(None))
        )
    ).scalar()

    # Route distribution
    route_rows = (
        await db.execute(
            select(RequestLog.route, func.count(RequestLog.id))
            .where(RequestLog.route.isnot(None))
            .group_by(RequestLog.route)
        )
    ).all()
    route_dist = {r: c for r, c in route_rows}

    # Feedback
    thumbs_up = (
        await db.execute(select(func.count(Feedback.id)).where(Feedback.rating == 1))
    ).scalar() or 0
    thumbs_down = (
        await db.execute(select(func.count(Feedback.id)).where(Feedback.rating == -1))
    ).scalar() or 0

    # Last eval run
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
        avg_latency_s=round(avg_latency, 2) if avg_latency else None,
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
    # Find the most recent directory matching the tag prefix
    candidates = sorted(EVAL_DIR.glob(f"{tag}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No eval dir found matching '{tag}' in {EVAL_DIR}")

    run_dir = candidates[0]
    metrics_file = run_dir / "metrics.json"
    if not metrics_file.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"metrics.json not found in {run_dir}")

    with metrics_file.open() as f:
        metrics_data: dict = json.load(f)

    # Read config snapshot for metadata
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
    # reload metrics
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
async def get_logs(limit: int = 200, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(RequestLog).order_by(RequestLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
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


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _eval_run_to_out(run: EvalRun) -> EvalRunOut:
    return EvalRunOut(
        id=run.id,
        tag=run.tag,
        chunking_strategy=run.chunking_strategy,
        sample_size=run.sample_size,
        created_at=run.created_at,
        metrics={m.metric_name: m.score for m in run.metrics},
    )
