"""Group grounding and answer failures by prompt version, not by top source.

Migration 0006 keyed every failing trace by its top retrieved source, so
unsupported claims with one cause, the prompt, but different top documents
showed up as separate one-trace issues. A
retrieval failure is about what was retrieved; a grounding or answer failure is
about how the answer was produced. Now:

- retrieval_miss, low_context_relevance, needs_review: label | top source
- unsupported_claim, wrong_answer: label | prompt version (or template name)

PostgreSQL 16 can't change a generated column's expression in place, so the
column is dropped and added again (one table rewrite). Resolved states for the
old grounding and answer keys no longer match an issue; their traces regroup.

Revision ID: 0007_issue_key_by_stage
Revises: 0006_issues
Create Date: 2026-11-16
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007_issue_key_by_stage"
down_revision: str | None = "0006_issues"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in step with ISSUE_KEY_SQL in app/db/models.py (a test compares them).
ISSUE_KEY = (
    "(CASE "
    "WHEN diagnosis_label IN ('retrieval_miss', 'low_context_relevance', 'needs_review') "
    "THEN diagnosis_label || '|' || COALESCE("
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_id', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'source', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_title', ''), "
    "'(no context)') "
    "WHEN diagnosis_label IN ('unsupported_claim', 'wrong_answer') "
    "THEN diagnosis_label || '|' || COALESCE("
    "NULLIF(payload -> 'prompt' ->> 'version', ''), "
    "NULLIF(payload -> 'prompt' ->> 'template_name', ''), "
    "'(no prompt version)') "
    "END)"
)

PREVIOUS = (
    "(CASE WHEN diagnosis_label IN "
    "('retrieval_miss', 'low_context_relevance', 'unsupported_claim', 'wrong_answer', 'needs_review') "
    "THEN diagnosis_label || '|' || COALESCE("
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_id', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'source', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_title', ''), "
    "'(no context)') END)"
)


def _replace(expression: str) -> None:
    op.drop_index("ix_traces_project_issue", table_name="traces")
    op.execute("ALTER TABLE traces DROP COLUMN issue_key")
    op.execute(f"ALTER TABLE traces ADD COLUMN issue_key text GENERATED ALWAYS AS {expression} STORED")
    op.execute(
        "CREATE INDEX ix_traces_project_issue ON traces (project_id, issue_key, created_at) "
        "WHERE issue_key IS NOT NULL"
    )


def upgrade() -> None:
    _replace(ISSUE_KEY)


def downgrade() -> None:
    _replace(PREVIOUS)
