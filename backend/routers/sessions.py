"""GET /sessions — list, detail, delete conversation sessions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models import Feedback, Message, Session
from backend.schemas import MessageOut, SessionDetail, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    # Count messages per session in one query
    count_q = (
        select(Message.session_id, func.count(Message.id).label("cnt"))
        .group_by(Message.session_id)
        .subquery()
    )
    q = (
        select(Session, count_q.c.cnt)
        .outerjoin(count_q, Session.id == count_q.c.session_id)
        .order_by(Session.updated_at.desc())
    )
    rows = (await db.execute(q)).all()
    out = []
    for sess, cnt in rows:
        out.append(
            SessionOut(
                id=sess.id,
                title=sess.title,
                created_at=sess.created_at,
                updated_at=sess.updated_at,
                message_count=cnt or 0,
            )
        )
    return out


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    q = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.messages).selectinload(Message.feedback))
    )
    session = (await db.execute(q)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages_out = []
    for msg in session.messages:
        fb_rating = msg.feedback.rating if msg.feedback else None
        messages_out.append(
            MessageOut(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                route=msg.route,
                latency_s=msg.latency_s,
                sources=msg.sources,
                feedback_rating=fb_rating,
            )
        )

    return SessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=len(session.messages),
        messages=messages_out,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()
