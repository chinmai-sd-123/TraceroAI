"""Store the diagnosis source and cost as generated columns.

The dashboard summary counts traces by diagnosis source and adds up cost. Read
from the JSON payload, both made Postgres decompress and parse every trace's
full payload (about 0.8 s at 50,000 traces). As stored generated columns they
stay in step with the payload on every insert and update, and the summary reads
only narrow columns.

Adding a stored generated column rewrites the table, holding an exclusive lock
while it does; on a large table, run this upgrade in a quiet period.

Revision ID: 0005_summary_columns
Revises: 0004_recovery_run_index
Create Date: 2026-11-16
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005_summary_columns"
down_revision: str | None = "0004_recovery_run_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIAGNOSIS_SOURCE = "(payload -> 'diagnosis' ->> 'source')"
# Only a JSON number becomes a cost; anything else is NULL rather than an error,
# so a malformed value can never make an insert fail.
COST_USD = (
    "(CASE WHEN jsonb_typeof(payload -> 'generation' -> 'usage' -> 'cost_usd') = 'number' "
    "THEN (payload -> 'generation' -> 'usage' ->> 'cost_usd')::double precision END)"
)


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE traces "
        f"ADD COLUMN diagnosis_source text GENERATED ALWAYS AS {DIAGNOSIS_SOURCE} STORED, "
        f"ADD COLUMN cost_usd double precision GENERATED ALWAYS AS {COST_USD} STORED"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE traces DROP COLUMN cost_usd, DROP COLUMN diagnosis_source")
