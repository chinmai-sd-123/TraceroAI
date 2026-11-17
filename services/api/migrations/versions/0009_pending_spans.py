"""OpenTelemetry ingest: spans waiting for the rest of their run.

OTLP exporters send spans in batches as they end, so one run's spans arrive
over several requests, children before the root. They wait in pending_spans
until the root arrives or the run has been quiet for a while, then become a
trace and its steps. Rows here are short-lived.

Revision ID: 0009_pending_spans
Revises: 0008_spans
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_pending_spans"
down_revision: str | None = "0008_spans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_spans",
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("span_id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(100), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column("step", postgresql.JSONB(), nullable=False),
        sa.Column("resource", postgresql.JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pending_spans_received_at", "pending_spans", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_pending_spans_received_at", table_name="pending_spans")
    op.drop_table("pending_spans")
