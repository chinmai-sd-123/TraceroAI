from __future__ import annotations
from collections.abc import Collection
from typing import Literal
from uuid import UUID


from sqlalchemy import Text, func, literal, select, update
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import TraceRecord
from app.schemas.traces import (
    DiagnosisTrace,
    EvaluationResult,
    FeedbackEntry,
    Trace,
)


class DuplicateTraceError(Exception):
    """A trace with this trace_id is already stored."""


class TraceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, trace: Trace) -> TraceRecord:
        payload = trace.model_dump(mode="json")

        record = TraceRecord(
            trace_id=trace.trace_id,
            schema_version=trace.schema_version,
            project_id=trace.project.project_id,
            environment=trace.project.environment,
            status=trace.status,
            query_text=trace.query.original,
            diagnosis_label=trace.diagnosis.label,
            model_name=trace.generation.model,
            total_latency_ms=trace.latency.total_ms,
            payload=payload,
        )

        self.db.add(record)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise DuplicateTraceError(f"Trace {trace.trace_id} already exists.") from error
        # No refresh: it would open a new transaction and keep a pooled connection
        # checked out for the rest of the request (e.g. during sync_deep_eval).

        return record

    def list(self, project_ids: Collection[str] | None = None) -> list[TraceRecord]:
        """Traces, newest first. project_ids=None means every project; an empty
        collection means none."""
        statement = select(TraceRecord).order_by(TraceRecord.created_at.desc())
        if project_ids is not None:
            statement = statement.where(TraceRecord.project_id.in_(sorted(project_ids)))
        return list(self.db.scalars(statement).all())

    def list_projects(self, project_ids: Collection[str] | None = None) -> list[str]:
        statement = (
            select(TraceRecord.project_id).distinct().order_by(TraceRecord.project_id)
        )
        if project_ids is not None:
            statement = statement.where(TraceRecord.project_id.in_(sorted(project_ids)))
        return list(self.db.scalars(statement).all())

    def get(self, trace_id: UUID) -> TraceRecord | None:
        return self.db.get(TraceRecord, trace_id)
    
    # The two writers below change one part of a stored trace each, and run while
    # other writers may be active (feedback arrives while the judge is running).
    # Each is a single UPDATE that sets only its own keys inside the JSONB payload,
    # so Postgres applies them one after the other and neither can overwrite the
    # other's change, without reading the payload into Python first.

    def set_evaluations(
        self,
        trace_id: UUID,
        *,
        quick: list[EvaluationResult] | None = None,
        deep: list[EvaluationResult] | None = None,
        diagnosis: DiagnosisTrace | None = None,
    ) -> bool:
        """Write background evaluation results. Each argument left as None keeps
        what's stored (e.g. no judge configured -> the deep list is untouched).
        Returns False if the trace doesn't exist."""
        payload = TraceRecord.payload
        columns: dict[str, object] = {}
        if quick is not None:
            payload = _jsonb_set(payload, ["evaluations", "quick"], _dump_list(quick))
        if deep is not None:
            payload = _jsonb_set(payload, ["evaluations", "deep"], _dump_list(deep))
        if diagnosis is not None:
            payload = _jsonb_set(payload, ["diagnosis"], diagnosis.model_dump(mode="json"))
            columns["diagnosis_label"] = diagnosis.label  # keep the indexed column in sync

        statement = update(TraceRecord).where(TraceRecord.trace_id == trace_id)
        return self._update(statement.values(payload=payload, **columns))

    def add_feedback(
        self,
        trace_id: UUID,
        entry: FeedbackEntry,
        *,
        project_id: str | None = None,
        max_entries: int | None = None,
    ) -> Literal["added", "missing", "full"]:
        """Append feedback, keeping at most max_entries on the trace.

        With project_id, a trace from another project is treated as missing, so
        a key can't reveal or touch other tenants' traces. The limit is checked
        in the same UPDATE, so concurrent posts can't overshoot it.
        """
        existing = func.coalesce(TraceRecord.payload["feedback"], literal([], JSONB))
        appended = existing.op("||", return_type=JSONB)(
            literal([entry.model_dump(mode="json")], JSONB)
        )
        statement = update(TraceRecord).where(TraceRecord.trace_id == trace_id)
        if project_id is not None:
            statement = statement.where(TraceRecord.project_id == project_id)
        if max_entries is not None:
            statement = statement.where(func.jsonb_array_length(existing) < max_entries)
        if self._update(
            statement.values(payload=_jsonb_set(TraceRecord.payload, ["feedback"], appended))
        ):
            return "added"

        record = self.get(trace_id)
        if record is None or (project_id is not None and record.project_id != project_id):
            return "missing"
        return "full"

    def _update(self, statement) -> bool:
        result = self.db.execute(
            statement.returning(TraceRecord.trace_id),
            execution_options={"synchronize_session": False},
        )
        found = result.first() is not None
        self.db.commit()
        return found


def _jsonb_set(target, path: list[str], value):
    """jsonb_set(target, path, value): replace the value at path inside target."""
    if not hasattr(value, "type"):  # a plain Python value, not a SQL expression
        value = literal(value, JSONB)
    return func.jsonb_set(target, literal(path, ARRAY(Text)), value, type_=JSONB)


def _dump_list(results: list[EvaluationResult]) -> list[dict]:
    return [result.model_dump(mode="json") for result in results]

