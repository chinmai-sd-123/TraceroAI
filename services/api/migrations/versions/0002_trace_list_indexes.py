"""Indexes for paginated trace lists.

Revision ID: 0002_trace_list_indexes
Revises: 0001_baseline
Create Date: 2026-11-13
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002_trace_list_indexes"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_traces_project_id_created_at", "traces", ["project_id", "created_at"])
    op.create_index("ix_traces_created_at", "traces", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_traces_created_at", table_name="traces")
    op.drop_index("ix_traces_project_id_created_at", table_name="traces")
