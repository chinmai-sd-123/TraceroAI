"""Alerts: what has been sent, so each alert goes out once.

One row per (project, kind, subject): a new issue that was announced (or was
already known when alerts were turned on), the last time a regression of an
issue was announced, and whether a project's failure rate is currently above
its threshold. A row with project "*" and kind "started" records when alerts
were first checked, so issues that existed before don't all arrive at once.

Revision ID: 0011_alert_states
Revises: 0010_run_cost
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_alert_states"
down_revision: str | None = "0010_run_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_states",
        sa.Column("project_id", sa.String(100), primary_key=True),
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("subject", sa.Text(), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("alert_states")
