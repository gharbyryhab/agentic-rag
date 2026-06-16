"""initial_schema

Revision ID: d1ce9f357e00
Revises:
Create Date: 2026-06-16 14:10:24.386570

This migration is intentionally idempotent: it inspects the live database
before every DDL statement so it is safe to apply to both:
  - a brand-new empty database  (creates everything from scratch)
  - a pre-Alembic database that was previously managed by SQLAlchemy
    create_all()  (skips tables that already exist and only adds the
    missing pieces — notably the `users` table and `sessions.user_id`)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1ce9f357e00"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    # ── eval_runs ────────────────────────────────────────────────────────────
    if "eval_runs" not in existing:
        op.create_table(
            "eval_runs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("tag", sa.String(), nullable=False),
            sa.Column("chunking_strategy", sa.String(), nullable=True),
            sa.Column("sample_size", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── users ────────────────────────────────────────────────────────────────
    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)

    # ── eval_metrics ─────────────────────────────────────────────────────────
    if "eval_metrics" not in existing:
        op.create_table(
            "eval_metrics",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("metric_name", sa.String(), nullable=False),
            sa.Column("score", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["eval_runs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── sessions ─────────────────────────────────────────────────────────────
    if "sessions" not in existing:
        op.create_table(
            "sessions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("sessions") as batch_op:
            batch_op.create_index(
                batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False
            )
    else:
        # Table pre-dates Alembic — patch in user_id if it is absent
        existing_cols = {c["name"] for c in inspector.get_columns("sessions")}
        if "user_id" not in existing_cols:
            with op.batch_alter_table("sessions") as batch_op:
                batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))
                batch_op.create_index(
                    batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False
                )
                batch_op.create_foreign_key("fk_sessions_user_id", "users", ["user_id"], ["id"])

    # ── messages ─────────────────────────────────────────────────────────────
    if "messages" not in existing:
        op.create_table(
            "messages",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("route", sa.String(), nullable=True),
            sa.Column("latency_s", sa.Float(), nullable=True),
            sa.Column("sources", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── request_logs ─────────────────────────────────────────────────────────
    if "request_logs" not in existing:
        op.create_table(
            "request_logs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("session_id", sa.String(), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("route", sa.String(), nullable=True),
            sa.Column("latency_s", sa.Float(), nullable=True),
            sa.Column("n_sources", sa.Integer(), nullable=True),
            sa.Column("online_judge_score", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    # ── feedback ─────────────────────────────────────────────────────────────
    if "feedback" not in existing:
        op.create_table(
            "feedback",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("message_id", sa.String(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("message_id"),
        )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("request_logs")
    op.drop_table("messages")
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))
    op.drop_table("sessions")
    op.drop_table("eval_metrics")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_email"))
    op.drop_table("users")
    op.drop_table("eval_runs")
