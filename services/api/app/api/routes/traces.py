from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.traces import TraceIngestRequest, TraceIngestResponse
from app.services.quick_evaluation import run_quick_evaluation
from app.services.trace_repository import TraceRepository
from app.services.deep_evaluation import run_deep_evaluation
from app.services.deep_eval_queue import enqueue_deep_eval_request


router = APIRouter(prefix="/v1/traces", tags=["traces"])

@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(
    payload: TraceIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> TraceIngestResponse:
    payload = run_quick_evaluation(payload)

    repository = TraceRepository(db)
    repository.save(payload)

    if not enqueue_deep_eval_request(payload.trace_id):
        background_tasks.add_task(run_deep_evaluation, payload.trace_id)

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
