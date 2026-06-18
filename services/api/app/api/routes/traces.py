from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenancy import project_for_api_key
from app.db.session import get_db
from app.schemas.traces import TraceIngestRequest, TraceIngestResponse, FeedbackEntry
from app.services.cost import compute_cost_usd
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
    authorization: str | None = Header(default=None),
) -> TraceIngestResponse:
    # Multi-tenant lite: resolve the API key to a project. When enforcement is on,
    # a missing/unknown key is rejected; otherwise it falls back to the client's
    # project. Either way, a known key means the server owns the attribution.
    project_id = project_for_api_key(authorization)

    if get_settings().require_api_key and project_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid project API key is required to send traces.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if project_id:
        payload.project.project_id = project_id

    # Cost is server-owned: fill total_tokens + cost_usd from the price table when
    # the client sent token counts but no cost (or none at all).
    usage = payload.generation.usage
    if usage.total_tokens is None and (
        usage.prompt_tokens is not None or usage.completion_tokens is not None
    ):
        usage.total_tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
    if usage.cost_usd is None:
        usage.cost_usd = compute_cost_usd(payload.generation.model, usage)

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
def list_traces(
    project_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    repository = TraceRepository(db)
    records = repository.list(project_id=project_id)

    return [record.payload for record in records]


@router.get("/projects", response_model=list[str])
def list_projects(db: Session = Depends(get_db)) -> list[str]:
    repository = TraceRepository(db)
    return repository.list_projects()


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

@router.post("/{trace_id}/feedback", status_code=status.HTTP_201_CREATED)
def add_feedback(
    trace_id: UUID,
    entry: FeedbackEntry,
    db: Session = Depends(get_db),
) -> FeedbackEntry:
    repository = TraceRepository(db)
    record = repository.add_feedback(trace_id, entry)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found.",
        )

    return entry

