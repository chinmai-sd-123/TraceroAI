"""Issues: group failing traces by a signature, and remember which were resolved.

A trace's issue key is its failure label plus the source of its top retrieved
chunk (for example "retrieval_miss|refunds.md"). It's a generated column, so a
trace moves to the right issue whenever its diagnosis changes (the LLM judge
replacing an estimate, say), without the ingest path or the worker doing
anything. Healthy traces have no issue key.

Only the resolved state is stored. Whether an issue is open, resolved or has
regressed is worked out when it's read, from that and the traces themselves.

Adding a stored generated column rewrites the traces table once.

Revision ID: 0006_issues
Revises: 0005_summary_columns
Create Date: 2026-11-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_issues"
down_revision: str | None = "0005_summary_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in step with app/services/issues.py (FAILURE_LABELS, the source fallback).
ISSUE_KEY = (
    "(CASE WHEN diagnosis_label IN "
    "('retrieval_miss', 'low_context_relevance', 'unsupported_claim', 'wrong_answer', 'needs_review') "
    "THEN diagnosis_label || '|' || COALESCE("
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_id', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'source', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_title', ''), "
    "'(no context)') END)"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE traces ADD COLUMN issue_key text GENERATED ALWAYS AS {ISSUE_KEY} STORED")
    op.execute(
        "CREATE INDEX ix_traces_project_issue ON traces (project_id, issue_key, created_at) "
        "WHERE issue_key IS NOT NULL"
    )
    op.create_table(
        "issue_states",
        sa.Column("project_id", sa.String(100), primary_key=True),
        sa.Column("issue_key", sa.Text(), primary_key=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("issue_states")
    op.drop_index("ix_traces_project_issue", table_name="traces")
    op.execute("ALTER TABLE traces DROP COLUMN issue_key")
