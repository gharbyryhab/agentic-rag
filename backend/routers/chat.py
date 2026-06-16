"""POST /chat — run a question through the RAG pipeline and persist the result."""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.auth import get_current_user
from backend.database import get_db
from backend.limiter import get_user_or_ip, limiter
from backend.models import Message, RequestLog, Session, User
from backend.schemas import ChatRequest, ChatResponse, SourceOut

router = APIRouter(prefix="/chat", tags=["chat"])

# Lazy-init: pipeline is heavy (BGE + ChromaDB + BM25), load once
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from src.pipeline import QueryPipeline
        _pipeline = QueryPipeline()
    return _pipeline


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute", key_func=get_user_or_ip)
async def chat(
    request: Request,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Load pipeline in a thread so the event loop is not blocked during model init
    pipeline = await asyncio.to_thread(_get_pipeline)

    # ── Resolve or create session ───────────────────────────────────────────
    if req.session_id:
        result = await db.execute(select(Session).where(Session.id == req.session_id))
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = Session(
            id=str(uuid.uuid4()),
            title=req.question[:60],
            user_id=current_user.id,
        )
        db.add(session)
        await db.flush()

    # ── Persist user message ────────────────────────────────────────────────
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=req.question,
    )
    db.add(user_msg)

    # ── Run RAG pipeline in thread pool (CPU/IO-bound, ~5-30s) ─────────────
    t0 = time.time()
    try:
        result = await asyncio.to_thread(pipeline.ask, req.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc
    latency = round(time.time() - t0, 2)

    answer = result.get("answer", "")
    route = result.get("route", "simple")
    sources_raw = result.get("sources", [])

    # ── Persist assistant message ───────────────────────────────────────────
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=answer,
        route=route,
        latency_s=latency,
        sources=sources_raw,
    )
    db.add(assistant_msg)

    # ── Update session updated_at ──────────────────────────────────────────
    await db.execute(
        update(Session)
        .where(Session.id == session.id)
        .values(updated_at=datetime.now(timezone.utc))
    )

    # ── Request log ────────────────────────────────────────────────────────
    log = RequestLog(
        session_id=session.id,
        question=req.question,
        route=route,
        latency_s=latency,
        n_sources=len(sources_raw),
    )
    db.add(log)

    await db.commit()
    await db.refresh(assistant_msg)

    sources_out = [
        SourceOut(
            source=s.get("source", ""),
            book_title=s.get("book_title", ""),
            page=str(s.get("page", "")),
            score=float(s.get("score", 0.0)),
            snippet=s.get("snippet", "")[:500],
        )
        for s in sources_raw
    ]

    return ChatResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        answer=answer,
        route=route,
        latency_s=latency,
        sources=sources_out,
    )


@router.post("/stream")
@limiter.limit("10/minute", key_func=get_user_or_ip)
async def chat_stream(
    request: Request,
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    async def _generate():
        pipeline = await asyncio.to_thread(_get_pipeline)

        # ── Resolve or create session ────────────────────────────────────────
        if req.session_id:
            r = await db.execute(select(Session).where(Session.id == req.session_id))
            session = r.scalar_one_or_none()
            if session is None:
                yield f'data: {json.dumps({"type": "error", "detail": "Session not found"})}\n\n'
                return
        else:
            session = Session(
                id=str(uuid.uuid4()),
                title=req.question[:60],
                user_id=current_user.id,
            )
            db.add(session)
            await db.flush()

        # ── Persist user message ─────────────────────────────────────────────
        db.add(Message(session_id=session.id, role="user", content=req.question))

        # ── Run pipeline concurrently, yielding keepalive pings every 2 s ───
        t0 = time.time()
        pipeline_task = asyncio.create_task(
            asyncio.to_thread(pipeline.ask, req.question)
        )
        while not pipeline_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(pipeline_task), timeout=2.0)
            except asyncio.TimeoutError:
                yield 'data: {"type":"ping"}\n\n'

        try:
            result = await pipeline_task
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "detail": f"Pipeline error: {exc}"})}\n\n'
            return

        latency = round(time.time() - t0, 2)
        answer = result.get("answer", "")
        route = result.get("route", "simple")
        sources_raw = result.get("sources", [])

        # ── Stream answer word by word (word-level sim — replace when Gemini streams) ──
        words = answer.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield f'data: {json.dumps({"type": "token", "value": token})}\n\n'
            await asyncio.sleep(0.02)

        # ── Persist assistant message + request log ──────────────────────────
        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content=answer,
            route=route,
            latency_s=latency,
            sources=sources_raw,
        )
        db.add(assistant_msg)
        await db.execute(
            update(Session)
            .where(Session.id == session.id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        db.add(RequestLog(
            session_id=session.id,
            question=req.question,
            route=route,
            latency_s=latency,
            n_sources=len(sources_raw),
        ))
        await db.commit()
        await db.refresh(assistant_msg)

        sources_out = [
            {
                "source": s.get("source", ""),
                "book_title": s.get("book_title", ""),
                "page": str(s.get("page", "")),
                "score": float(s.get("score", 0.0)),
                "snippet": s.get("snippet", "")[:500],
            }
            for s in sources_raw
        ]

        # ── Done event ───────────────────────────────────────────────────────
        yield f'data: {json.dumps({"type": "done", "message_id": assistant_msg.id, "session_id": session.id, "route": route, "latency_s": latency, "sources": sources_out})}\n\n'

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
