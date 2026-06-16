"""Auth routes: register, login, profile, update email/password, sign out."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import create_access_token, get_current_user, hash_password, verify_password
from backend.database import get_db
from backend.limiter import limiter
from backend.models import Message, Session, User
from backend.schemas import (
    ProfileOut, TokenOut, UpdateEmail, UpdatePassword, UserLogin, UserRegister,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Register ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit("5/hour")
async def register(
    request: Request,
    req: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(select(User).where(User.email == req.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    # First ever user becomes admin
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    role = "admin" if user_count == 0 else "user"
    user = User(email=req.email, password_hash=hash_password(req.password), role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenOut(
        access_token=create_access_token(user.id),
        token_type="bearer",
        user_id=user.id,
        role=user.role,
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
async def login(
    request: Request,
    req: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    user = (
        await db.execute(select(User).where(User.email == req.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account disabled")
    return TokenOut(
        access_token=create_access_token(user.id),
        token_type="bearer",
        user_id=user.id,
        role=user.role,
    )


# ── Get profile ───────────────────────────────────────────────────────────────

@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_sessions = (
        await db.execute(
            select(func.count(Session.id)).where(Session.user_id == current_user.id)
        )
    ).scalar() or 0

    total_questions = (
        await db.execute(
            select(func.count(Message.id))
            .join(Session, Message.session_id == Session.id)
            .where(Session.user_id == current_user.id, Message.role == "user")
        )
    ).scalar() or 0

    return ProfileOut(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        total_sessions=total_sessions,
        total_questions=total_questions,
    )


# ── Update email ──────────────────────────────────────────────────────────────

@router.patch("/profile/email", response_model=ProfileOut)
async def update_email(
    req: UpdateEmail,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check not taken by someone else
    existing = (
        await db.execute(
            select(User).where(User.email == req.email, User.id != current_user.id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")

    current_user.email = req.email
    await db.commit()
    await db.refresh(current_user)
    return await get_profile(current_user, db)


# ── Update password ───────────────────────────────────────────────────────────

@router.patch("/profile/password")
async def update_password(
    req: UpdatePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = hash_password(req.new_password)
    await db.commit()
    return {"detail": "Password updated successfully"}


# ── Delete account ────────────────────────────────────────────────────────────

@router.delete("/profile", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(current_user)
    await db.commit()
