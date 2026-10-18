from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.tenancy import optional_project, write_project
from app.db.session import get_db
from app.schemas.traces import (
    FeedbackEntry,
    FeedbackRequest,
    TraceIngestRequest,
    TraceIngestResponse,
)
from app.services.cost import compute_cost_usd
from app.services.quick_evaluation import run_quick_evaluation
from app.services.rate_limiter import check_rate_limit, client_ip
from app.services.trace_repository import TraceRepository
from app.services.deep_evaluation import run_deep_evaluation
from app.services.deep_eval_queue import enqueue_deep_eval_request


router = APIRouter(prefix="/v1/traces", tags=["traces"])

# Keyless feedback (the public dashboard's thumbs widget) is rate-limited per IP.
ANONYMOUS_FEEDBACK_LIMIT = 10
ANONYMOUS_FEEDBACK_WINDOW_SECONDS = 60


@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(
    payload: TraceIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    project_id: str | None = Depends(write_project),
    sync_deep_eval: bool = False,
) -> TraceIngestResponse:
    # A known key means the server owns the attribution; without one (allowed only
    # when keys aren't required) the client-provided project is kept.
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

    # Lexical-only on the request path: no network call, so a slow or down
    # embeddings provider can't slow ingest. The background pass re-runs the quick
    # evaluators with embeddings, then the LLM judge.
    payload = run_quick_evaluation(payload, semantic=False)

    repository = TraceRepository(db)
    repository.save(payload)

    # Synchronous deep eval (e.g. for the recovery agent, which must route on a
    # judge-quality diagnosis NOW rather than poll an async queue). Run the judge
    # inline and return the corrected diagnosis in the response. If it fails for any
    # reason, fall back to the async path and return the quick diagnosis — never hang
    # or break the caller.
    diagnosis = payload.diagnosis
    if sync_deep_eval:
        try:
            run_deep_evaluation(payload.trace_id)
            record = repository.get(payload.trace_id)
            if record is not None:
                diagnosis = TraceIngestRequest(**record.payload).diagnosis
        except Exception:
            # inline judge failed — leave the quick diagnosis and let async retry
            if not enqueue_deep_eval_request(payload.trace_id):
                background_tasks.add_task(run_deep_evaluation, payload.trace_id)
    elif not enqueue_deep_eval_request(payload.trace_id):
        background_tasks.add_task(run_deep_evaluation, payload.trace_id)

    return TraceIngestResponse(
        trace_id=payload.trace_id,
        status="accepted",
        message="Trace accepted for ingestion.",
        diagnosis=diagnosis,
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
    body: FeedbackRequest,
    request: Request,
    db: Session = Depends(get_db),
    project_id: str | None = Depends(optional_project),
) -> FeedbackEntry:
    # Feedback costs no LLM calls, so the dashboard widget may send it without a
    # key (browsers can't hold one) — but keyless calls are rate-limited per IP.
    # With a key, feedback is scoped to that key's project.
    if project_id is None and not check_rate_limit(
        bucket="feedback",
        identity=client_ip(request),
        limit=ANONYMOUS_FEEDBACK_LIMIT,
        window_seconds=ANONYMOUS_FEEDBACK_WINDOW_SECONDS,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too much feedback from this address — please wait a minute.",
        )

    entry = FeedbackEntry(rating=body.rating, comment=body.comment)
    repository = TraceRepository(db)
    record = repository.add_feedback(trace_id, entry, project_id=project_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found.",
        )

    return entry

