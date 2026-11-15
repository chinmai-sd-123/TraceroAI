"""Index recovery-run attempts by run id.

Revision ID: 0004_recovery_run_index
Revises: 0003_api_keys
Create Date: 2026-11-14
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004_recovery_run_index"
down_revision: str | None = "0003_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only recovery attempts carry a run id, so a partial index stays small.
    op.execute(
        "CREATE INDEX ix_traces_recovery_run_id ON traces "
        "((payload -> 'metadata' ->> 'recovery_run_id')) "
        "WHERE payload -> 'metadata' ->> 'recovery_run_id' IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_traces_recovery_run_id", table_name="traces")
