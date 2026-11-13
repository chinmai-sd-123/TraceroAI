"""Baseline: the traces and eval_runs tables.

Before Alembic, tables were created with Base.metadata.create_all. Databases
set up that way already have both tables, so each one is created only if it is
missing; running this against such a database just records the revision.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if "traces" not in existing:
        op.create_table(
            "traces",
            sa.Column("trace_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("schema_version", sa.String(), nullable=False),
            sa.Column("project_id", sa.String(100), nullable=False),
            sa.Column("environment", sa.String(50), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("query_text", sa.String(), nullable=False),
            sa.Column("diagnosis_label", sa.String(100), nullable=True),
            sa.Column("model_name", sa.String(100), nullable=True),
            sa.Column("total_latency_ms", sa.Integer(), nullable=True),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        for column in ("trace_id", "project_id", "environment", "status", "diagnosis_label"):
            op.create_index(f"ix_traces_{column}", "traces", [column])

    if "eval_runs" not in existing:
        op.create_table(
            "eval_runs",
            sa.Column("eval_run_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("schema_version", sa.String(), nullable=False),
            sa.Column("run_type", sa.String(50), nullable=False),
            sa.Column("status", sa.String(50), nullable=False),
            sa.Column("project_id", sa.String(100), nullable=False),
            sa.Column("environment", sa.String(50), nullable=False),
            sa.Column("dataset_id", sa.String(100), nullable=False),
            sa.Column("dataset_name", sa.String(200), nullable=False),
            sa.Column("dataset_version", sa.String(100), nullable=True),
            sa.Column("pipeline_version", sa.String(100), nullable=False),
            sa.Column("baseline_pipeline_version", sa.String(100), nullable=True),
            sa.Column("total_cases", sa.Integer(), nullable=False),
            sa.Column("passed_cases", sa.Integer(), nullable=False),
            sa.Column("failed_cases", sa.Integer(), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        for column in (
            "eval_run_id",
            "run_type",
            "status",
            "project_id",
            "environment",
            "dataset_id",
            "pipeline_version",
        ):
            op.create_index(f"ix_eval_runs_{column}", "eval_runs", [column])


def downgrade() -> None:
    op.drop_table("eval_runs")
    op.drop_table("traces")
