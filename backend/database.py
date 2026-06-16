"""Async SQLAlchemy engine — supports SQLite (dev) and PostgreSQL (prod)."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_URL = f"sqlite+aiosqlite:///{_ROOT / 'data' / 'app.db'}"

# Single source of truth: read once at import time.
DATABASE_URL: str = os.environ.get("DATABASE_URL", _DEFAULT_URL)

# Ensure the parent directory exists for SQLite databases.
if DATABASE_URL.startswith("sqlite"):
    _db_path = DATABASE_URL.split("///", 1)[-1]
    Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Dev-only fallback: auto-create tables without Alembic.

    In production, run ``alembic upgrade head`` instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite doesn't support ADD COLUMN IF NOT EXISTS — catch the error gracefully
        if DATABASE_URL.startswith("sqlite"):
            try:
                await conn.exec_driver_sql(
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
                )
            except Exception:
                pass  # column already exists


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency — yields a DB session."""
    async with SessionLocal() as session:
        yield session
