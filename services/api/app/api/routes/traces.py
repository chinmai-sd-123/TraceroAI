from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.traces import TraceIngestRequest, TraceIngestResponse
from app.services.trace_repository import TraceRepository

router = APIRouter(prefix="/v1/traces", tags=["traces"])

@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(
    payload: TraceIngestRequest,
    db: Session = Depends(get_db),
) -> TraceIngestResponse:
    repository = TraceRepository(db)
    repository.save(payload)

    return TraceIngestResponse(
        trace_id=payload.trace_id,
        status="accepted",
        message="Trace accepted for ingestion.",
    )


@router.get("", response_model=list[TraceIngestRequest])
def list_traces(db: Session = Depends(get_db)) -> list[dict]:
    repository = TraceRepository(db)
    records = repository.list()

    return [record.payload for record in records]


@router.get("/{trace_id}", response_model=TraceIngestRequest)
def get_trace(
    trace_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    repository = TraceRepository(db)
    record = repository.get(trace_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found.",
        )

    return record.payload
