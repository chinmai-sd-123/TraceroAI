from datetime import datetime
from uuid import UUID as PythonUUID

from sqlalchemy import Computed, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

# Must match migration 0006_issues (and FAILURE_LABELS in app/services/issues.py).
ISSUE_KEY_SQL = (
    "(CASE WHEN diagnosis_label IN "
    "('retrieval_miss', 'low_context_relevance', 'unsupported_claim', 'wrong_answer', 'needs_review') "
    "THEN diagnosis_label || '|' || COALESCE("
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_id', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'source', ''), "
    "NULLIF(payload -> 'retrieval' -> 'chunks' -> 0 ->> 'document_title', ''), "
    "'(no context)') END)"
)


class TraceRecord(Base):
    __tablename__ = "traces"
    # Trace lists are newest first, usually within one project (see
    # app/services/trace_query.py); these keep a page an index range scan.
    __table_args__ = (
        Index("ix_traces_project_id_created_at", "project_id", "created_at"),
        Index("ix_traces_created_at", "created_at"),
    )

    trace_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    query_text: Mapped[str] = mapped_column(String, nullable=False)
    diagnosis_label: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_latency_ms: Mapped[int|None] = mapped_column(Integer, nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Kept in step with the payload by Postgres (migration 0005), so the summary
    # never has to parse every payload. Read-only: never set these directly.
    diagnosis_source: Mapped[str | None] = mapped_column(
        Text, Computed("(payload -> 'diagnosis' ->> 'source')", persisted=True)
    )
    cost_usd: Mapped[float | None] = mapped_column(
        Float,
        Computed(
            "(CASE WHEN jsonb_typeof(payload -> 'generation' -> 'usage' -> 'cost_usd') = 'number' "
            "THEN (payload -> 'generation' -> 'usage' ->> 'cost_usd')::double precision END)",
            persisted=True,
        ),
    )

    # The issue this trace belongs to when it failed (migration 0006): its failure
    # label plus the source of its top chunk. Read-only, kept in step by Postgres.
    issue_key: Mapped[str | None] = mapped_column(Text, Computed(ISSUE_KEY_SQL, persisted=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False,)


class EvalRunRecord(Base):
    __tablename__ = "eval_runs"

    eval_run_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    dataset_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    dataset_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    baseline_pipeline_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class ApiKeyRecord(Base):
    """An API key. Only a hash of the key is stored; the key itself is shown
    once, when it's created (python -m app.keys create)."""

    __tablename__ = "api_keys"

    key_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # SHA-256 of the full key. Keys are long random strings, so a fast hash is
    # enough: there is nothing to guess from.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # The first characters of the key, so people can tell keys apart.
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # "project": reads and writes one project. "admin": reads every project.
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IssueStateRecord(Base):
    """Whether an issue was marked resolved, and when (migration 0006). An issue
    with failures after resolved_at has regressed; see app/services/issues.py."""

    __tablename__ = "issue_states"

    project_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    issue_key: Mapped[str] = mapped_column(Text, primary_key=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
