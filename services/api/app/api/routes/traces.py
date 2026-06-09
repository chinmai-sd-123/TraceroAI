from fastapi import APIRouter, status, HTTPException
from uuid import UUID
from app.schemas.traces import TraceIngestRequest, TraceIngestResponse
from app.services.trace_store import trace_store
router= APIRouter(prefix="/v1/traces", tags=["traces"])

@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(payload: TraceIngestRequest)-> TraceIngestResponse:
    trace_store.save(payload)
    return TraceIngestResponse(
        trace_id=payload.trace_id,
        status="accepted",
        message="Trace accepted for ingestion.",
    )

@router.get("", response_model=list[TraceIngestRequest])
def list_traces() -> list[TraceIngestRequest]:
    return trace_store.list()

@router.get("/{trace_id}", response_model=TraceIngestRequest)
def get_trace(trace_id: UUID) -> TraceIngestRequest:
    trace = trace_store.get(trace_id)

    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found.",
        )

    return trace