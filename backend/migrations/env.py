"""Alembic migration environment.

Supports:
  - SQLite + aiosqlite  (dev default)
  - PostgreSQL + asyncpg (production)

DATABASE_URL is read from the environment (via backend.database) so there is
a single source of truth — never hardcode the URL here or in alembic.ini.
"""
from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Make sure project root is importable ─────────────────────────────────────
# env.py lives at  <root>/backend/migrations/env.py
# parents[2]  →   <root>/
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ── Import models BEFORE Base so all tables are registered ───────────────────
from backend.database import Base, DATABASE_URL  # noqa: E402
import backend.models  # noqa: E402, F401 — side-effect: registers ORM classes

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the resolved URL so alembic.ini never needs to be touched
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = Base.metadata


# ── Offline mode ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (useful for dry-runs)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # batch mode lets Alembic emulate ALTER TABLE on SQLite
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online (async) mode ───────────────────────────────────────────────────────
def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside a sync wrapper."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
