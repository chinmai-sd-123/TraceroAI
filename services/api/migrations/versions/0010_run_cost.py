"""A run's cost: every model call in it, not only its single answer.

An agent run has several model calls and no single answer, so pricing only
generation.usage left it without a cost. A trace's cost is now run_usage.cost_usd
(the sum of its priced model-call steps, set when a run arrives over
OpenTelemetry) when present, else generation.usage.cost_usd as before.

Re-adding a stored generated column rewrites the traces table once.

Revision ID: 0010_run_cost
Revises: 0009_pending_spans
Create Date: 2026-11-17
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010_run_cost"
down_revision: str | None = "0009_pending_spans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Keep in step with TraceRecord.cost_usd in app/db/models.py.
COST_USD = (
    "(CASE WHEN jsonb_typeof(payload -> 'run_usage' -> 'cost_usd') = 'number' "
    "THEN (payload -> 'run_usage' ->> 'cost_usd')::double precision "
    "WHEN jsonb_typeof(payload -> 'generation' -> 'usage' -> 'cost_usd') = 'number' "
    "THEN (payload -> 'generation' -> 'usage' ->> 'cost_usd')::double precision END)"
)
PREVIOUS = (
    "(CASE WHEN jsonb_typeof(payload -> 'generation' -> 'usage' -> 'cost_usd') = 'number' "
    "THEN (payload -> 'generation' -> 'usage' ->> 'cost_usd')::double precision END)"
)


def upgrade() -> None:
    op.execute("ALTER TABLE traces DROP COLUMN cost_usd")
    op.execute(f"ALTER TABLE traces ADD COLUMN cost_usd double precision GENERATED ALWAYS AS {COST_USD} STORED")


def downgrade() -> None:
    op.execute("ALTER TABLE traces DROP COLUMN cost_usd")
    op.execute(f"ALTER TABLE traces ADD COLUMN cost_usd double precision GENERATED ALWAYS AS {PREVIOUS} STORED")
