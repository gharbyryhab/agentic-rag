"""GET/PATCH/DELETE /sessions — list, detail, rename, delete conversation sessions."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Feedback, Message, Session, User
from backend.schemas import (
    MessageOut,
    PaginatedResponse,
    SessionDetail,
    SessionOut,
    SessionRename,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=PaginatedResponse[SessionOut])
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conditions = [Session.user_id == current_user.id]
    if search:
        conditions.append(Session.title.ilike(f"%{search}%"))

    # Total count with applied filters
    total = (
        await db.execute(select(func.count(Session.id)).where(*conditions))
    ).scalar() or 0
    pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    # Message count per session via subquery
    count_sub = (
        select(Message.session_id, func.count(Message.id).label("cnt"))
        .group_by(Message.session_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Session, count_sub.c.cnt)
            .outerjoin(count_sub, Session.id == count_sub.c.session_id)
            .where(*conditions)
            .order_by(Session.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).all()

    items = [
        SessionOut(
            id=sess.id,
            title=sess.title,
            created_at=sess.created_at,
            updated_at=sess.updated_at,
            message_count=cnt or 0,
        )
        for sess, cnt in rows
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(Session)
        .where(Session.id == session_id, Session.user_id == current_user.id)
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


@router.patch("/{session_id}", response_model=SessionOut)
async def rename_session(
    session_id: str,
    body: SessionRename,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = body.title
    await db.commit()
    await db.refresh(session)

    cnt = (
        await db.execute(
            select(func.count(Message.id)).where(Message.session_id == session_id)
        )
    ).scalar() or 0

    return SessionOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=cnt,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.execute(delete(Session).where(Session.id == session_id))
    await db.commit()
