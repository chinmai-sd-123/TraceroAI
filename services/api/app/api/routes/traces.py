import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenancy import (
    Caller,
    ReadScope,
    api_key_required,
    caller,
    read_scope,
    write_project,
)
from app.db.session import get_db
from app.db.models import TraceRecord
from app.schemas.traces import (
    FeedbackEntry,
    FeedbackRequest,
    Trace,
    TraceIngestRequest,
    TraceIngestResponse,
)
from app.services.cost import compute_cost_usd
from app.services.quick_evaluation import run_quick_evaluation
from app.services.rate_limiter import check_rate_limit, client_ip
from app.services.trace_repository import DuplicateTraceError, TraceRepository
from app.services.deep_evaluation import run_deep_evaluation
from app.services.deep_eval_queue import enqueue_deep_eval_request
from app.services.fallback_evaluation import submit_fallback_evaluation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/traces", tags=["traces"])

# Keyless feedback (the public dashboard's thumbs widget) is rate-limited per IP.
ANONYMOUS_FEEDBACK_LIMIT = 10
ANONYMOUS_FEEDBACK_WINDOW_SECONDS = 60


@router.post("", response_model=TraceIngestResponse, status_code=status.HTTP_202_ACCEPTED)
def ingest_trace(
    payload: TraceIngestRequest,
    db: Session = Depends(get_db),
    project_id: str | None = Depends(write_project),
    sync_deep_eval: bool = False,
) -> TraceIngestResponse:
    # A known key means the server owns the attribution; without one (allowed only
    # when keys aren't required) the client-provided project is kept.
    if project_id:
        payload.project.project_id = project_id

    repository = TraceRepository(db)

    # Idempotent on trace_id: a client retrying after a timeout gets the stored
    # trace back instead of creating a duplicate (and paying for a second judge run).
    existing = repository.get(payload.trace_id)
    if existing is not None:
        return _already_ingested(existing, payload.project.project_id)

    trace = Trace(**payload.model_dump())

    # Cost is server-owned: fill total_tokens + cost_usd from the price table when
    # the client sent token counts but no cost (or none at all).
    usage = trace.generation.usage
    if usage.total_tokens is None and (
        usage.prompt_tokens is not None or usage.completion_tokens is not None
    ):
        usage.total_tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
    if usage.cost_usd is None:
        usage.cost_usd = compute_cost_usd(trace.generation.model, usage)

    # Lexical-only on the request path: no network call, so a slow or down
    # embeddings provider can't slow ingest. The background pass re-runs the quick
    # evaluators with embeddings, then the LLM judge.
    trace = run_quick_evaluation(trace, semantic=False)

    try:
        repository.save(trace)
    except DuplicateTraceError:
        # A concurrent request with the same trace_id inserted first.
        stored = repository.get(trace.trace_id)
        if stored is None:  # pragma: no cover - the row we collided with is gone
            raise
        return _already_ingested(stored, trace.project.project_id)

    # Synchronous deep eval (e.g. for the recovery agent, which must route on a
    # judge-quality diagnosis NOW rather than poll an async queue). Run the judge
    # inline and return the corrected diagnosis in the response. If it fails for any
    # reason, fall back to the async path and return the quick diagnosis — never hang
    # or break the caller.
    diagnosis = trace.diagnosis
    if sync_deep_eval:
        try:
            run_deep_evaluation(trace.trace_id, inline=True)
            record = repository.get(trace.trace_id)
            if record is not None:
                diagnosis = Trace(**record.payload).diagnosis
        except Exception:
            logger.exception("Inline deep evaluation failed for %s", trace.trace_id)
            # Leave the quick diagnosis and evaluate again off the request path.
            if not enqueue_deep_eval_request(trace.trace_id):
                submit_fallback_evaluation(trace.trace_id)
    elif not enqueue_deep_eval_request(trace.trace_id):
        submit_fallback_evaluation(trace.trace_id)

    return TraceIngestResponse(
        trace_id=trace.trace_id,
        status="accepted",
        message="Trace accepted for ingestion.",
        diagnosis=diagnosis,
    )


def _already_ingested(record: TraceRecord, project_id: str) -> TraceIngestResponse:
    """Response for a trace_id that is already stored.

    Same project: the earlier result, so a retry looks like the first success.
    Different project: 409, since ids aren't shared between projects.
    """
    if record.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A trace with this trace_id already exists.",
        )
    return TraceIngestResponse(
        trace_id=record.trace_id,
        status="accepted",
        message="Trace already ingested.",
        diagnosis=Trace(**record.payload).diagnosis,
    )



@router.get("", response_model=list[Trace])
def list_traces(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> list[dict]:
    repository = TraceRepository(db)
    records = repository.list(project_ids=scope.narrow(project_id))

    return [record.payload for record in records]


@router.get("/projects", response_model=list[str])
def list_projects(
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> list[str]:
    repository = TraceRepository(db)
    return repository.list_projects(project_ids=scope.projects)


@router.get("/{trace_id}", response_model=Trace)
def get_trace(
    trace_id: UUID,
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> dict:
    repository = TraceRepository(db)
    record = repository.get(trace_id)

    # A trace outside the caller's projects is reported as missing, not
    # forbidden, so a key can't confirm that someone else's trace exists.
    if record is None or not scope.allows(record.project_id):
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
    who: Caller = Depends(caller),
) -> FeedbackEntry:
    # With a project key, feedback is limited to that project's traces; an admin
    # key (the dashboard's server) may add it to any trace. Without a key it's
    # allowed only where keys aren't required (local development), and then
    # rate-limited per IP.
    if who.anonymous:
        if api_key_required():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid API key is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not check_rate_limit(
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
    outcome = repository.add_feedback(
        trace_id,
        entry,
        project_id=who.project_id,
        max_entries=get_settings().max_feedback_per_trace,
    )
    if outcome == "missing":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trace not found.",
        )
    if outcome == "full":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This trace already has the maximum amount of feedback.",
        )

    return entry

