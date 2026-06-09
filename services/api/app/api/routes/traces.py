from fastapi import APIRouter, status

from app.schemas.traces import TraceIngestRequest, TraceIngestResponse
router= APIRouter(prefix="/v1/traces", tags=["traces"])

@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(payload: TraceIngestRequest)-> TraceIngestResponse:
    return TraceIngestResponse(
        trace_id=payload.trace_id,
        status="accepted",
        message="Trace accepted for ingestion.",
    )