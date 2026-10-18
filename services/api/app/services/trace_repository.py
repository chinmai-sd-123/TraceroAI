from __future__ import annotations
from uuid import UUID


from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TraceRecord
from app.schemas.traces import (
    DiagnosisTrace,
    EvaluationResult,
    FeedbackEntry,
    TraceIngestRequest,
)


class TraceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, trace: TraceIngestRequest) -> TraceRecord:
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
        self.db.commit()
        self.db.refresh(record)

        return record

    def list(self, project_id: str | None = None) -> list[TraceRecord]:
        statement = select(TraceRecord).order_by(TraceRecord.created_at.desc())
        if project_id:
            statement = statement.where(TraceRecord.project_id == project_id)
        return list(self.db.scalars(statement).all())

    def list_projects(self) -> list[str]:
        statement = (
            select(TraceRecord.project_id).distinct().order_by(TraceRecord.project_id)
        )
        return list(self.db.scalars(statement).all())

    def get(self, trace_id: UUID) -> TraceRecord | None:
        return self.db.get(TraceRecord, trace_id)
    
    def set_evaluations(
        self,
        trace_id: UUID,
        *,
        quick: list[EvaluationResult] | None = None,
        deep: list[EvaluationResult] | None = None,
        diagnosis: DiagnosisTrace | None = None,
    ) -> TraceRecord | None:
        """Write background evaluation results. Each argument left as None keeps
        what's stored (e.g. no judge configured -> the deep list is untouched)."""
        record = self.db.get(TraceRecord, trace_id)
        if record is None:
            return None

        trace = TraceIngestRequest(**record.payload)
        if quick is not None:
            trace.evaluations.quick = quick
        if deep is not None:
            trace.evaluations.deep = deep
        if diagnosis is not None:
            trace.diagnosis = diagnosis
            record.diagnosis_label = diagnosis.label  # keep the indexed column in sync
        record.payload = trace.model_dump(mode="json")

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def add_feedback(
        self, trace_id: UUID, entry: FeedbackEntry, *, project_id: str | None = None
    ) -> TraceRecord | None:
        """Append feedback. With project_id, a trace from another project is
        treated as missing, so a key can't reveal or touch other tenants' traces."""
        record = self.db.get(TraceRecord, trace_id)
        if record is None or (project_id is not None and record.project_id != project_id):
            return None

        trace = TraceIngestRequest(**record.payload)
        trace.feedback.append(entry)
        record.payload = trace.model_dump(mode="json")

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

