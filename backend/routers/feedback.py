"""POST /messages/{id}/feedback — thumbs up/down on an assistant message."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import Feedback, Message, User
from backend.schemas import FeedbackOut, FeedbackRequest

router = APIRouter(prefix="/messages", tags=["feedback"])


@router.post("/{message_id}/feedback", response_model=FeedbackOut)
async def submit_feedback(
    message_id: str,
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify message exists and is from assistant
    msg = (await db.execute(select(Message).where(Message.id == message_id))).scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="Feedback can only be given on assistant messages")

    # Upsert feedback
    existing = (
        await db.execute(select(Feedback).where(Feedback.message_id == message_id))
    ).scalar_one_or_none()

    if existing:
        existing.rating = req.rating
        existing.comment = req.comment
        fb = existing
    else:
        fb = Feedback(message_id=message_id, rating=req.rating, comment=req.comment)
        db.add(fb)

    await db.commit()
    await db.refresh(fb)
    return fb
