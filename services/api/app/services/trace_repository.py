from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TraceRecord
from app.schemas.traces import TraceIngestRequest


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

    def list(self) -> list[TraceRecord]:
        statement = select(TraceRecord).order_by(TraceRecord.created_at.desc())
        return list(self.db.scalars(statement).all())

    def get(self, trace_id: UUID) -> TraceRecord | None:
        return self.db.get(TraceRecord, trace_id)