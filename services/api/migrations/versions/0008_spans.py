"""Steps: a trace becomes a summary row plus a tree of steps (docs/adr/0002).

Each step is a row in `spans`, keyed by its trace and its own id, with its
parent, kind, timing, status, input, output and attributes. Deleting a trace
deletes its steps.

Traces stored before this migration get no steps here: the API derives them
when such a trace is read without any.

Revision ID: 0008_spans
Revises: 0007_issue_key_by_stage
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_spans"
down_revision: str | None = "0007_issue_key_by_stage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spans",
        sa.Column(
            "trace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("traces.trace_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("span_id", sa.String(64), primary_key=True),
        sa.Column("parent_span_id", sa.String(64), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("status_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("spans")
