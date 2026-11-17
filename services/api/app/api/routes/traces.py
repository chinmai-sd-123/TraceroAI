import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.metrics import TRACES_INGESTED
from app.core.tenancy import (
    Caller,
    ReadScope,
    api_key_required,
    caller,
    rate_limit,
    read_scope,
    write_project,
)
from app.db.session import get_db
from app.db.models import TraceRecord
from app.schemas.traces import (
    FeedbackEntry,
    FeedbackRequest,
    Trace,
    TraceDetail,
    TraceIngestRequest,
    TraceIngestResponse,
)
from app.services.cost import compute_cost_usd
from app.services.quick_evaluation import run_quick_evaluation
from app.services.rate_limiter import check_rate_limit, client_ip
from app.services.steps import as_step, derive_steps, to_step
from app.services.trace_query import InvalidCursor, TraceFilters, TraceSort, list_page
from app.services.trace_repository import DuplicateTraceError, TraceRepository
from app.services.deep_evaluation import (
    initial_deep_status,
    judge_configured,
    run_deep_evaluation,
)
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
    _limit: None = Depends(rate_limit("ingest", "ingest_rate_limit_per_minute")),
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
        TRACES_INGESTED.labels("duplicate").inc()
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
    trace.evaluations.deep_status = initial_deep_status()

    try:
        repository.save(trace, steps=payload.steps)
    except DuplicateTraceError:
        # A concurrent request with the same trace_id inserted first.
        stored = repository.get(trace.trace_id)
        if stored is None:  # pragma: no cover - the row we collided with is gone
            raise
        TRACES_INGESTED.labels("duplicate").inc()
        return _already_ingested(stored, trace.project.project_id)
    TRACES_INGESTED.labels("stored").inc()

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
    elif judge_configured() and not enqueue_deep_eval_request(trace.trace_id):
        # Without a provider key there is nothing to do in the background: the
        # trace keeps its lexical diagnosis and deep_status "skipped".
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
    response: Response,
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    diagnosis: str | None = None,
    model: str | None = None,
    environment: str | None = None,
    q: str | None = Query(default=None, max_length=200, description="Text in the query"),
    since: datetime | None = None,
    until: datetime | None = None,
    sort: TraceSort = "newest",
    recovery_run_id: str | None = Query(default=None, max_length=100, description="Attempts of one recovery run"),
    issue_key: str | None = Query(default=None, max_length=2000, description="Traces in one issue"),
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> list[dict]:
    """Traces one page at a time: newest first (default), oldest first, or
    slowest first.

    When there are more, the X-Next-Cursor response header holds the value to
    pass as ?cursor= for the next page.
    """
    filters = TraceFilters(
        project_ids=scope.narrow(project_id),
        diagnosis=diagnosis,
        model=model,
        environment=environment,
        text=q,
        since=since,
        until=until,
        recovery_run_id=recovery_run_id,
        issue_key=issue_key,
    )
    try:
        records, next_cursor = list_page(db, filters, limit=limit, cursor=cursor, sort=sort)
    except InvalidCursor as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if next_cursor:
        response.headers["X-Next-Cursor"] = next_cursor
    return [record.payload for record in records]


@router.get("/projects", response_model=list[str])
def list_projects(
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> list[str]:
    repository = TraceRepository(db)
    return repository.list_projects(project_ids=scope.projects)


@router.get("/{trace_id}", response_model=TraceDetail)
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

    # Traces stored before steps existed have none in the table; derive them.
    stored = repository.steps(trace_id)
    steps = [to_step(step) for step in stored] if stored else [as_step(step) for step in derive_steps(Trace(**record.payload))]
    return {**record.payload, "steps": [step.model_dump(mode="json") for step in steps]}

@router.delete("/{trace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trace(
    trace_id: UUID,
    db: Session = Depends(get_db),
    project_id: str | None = Depends(write_project),
) -> Response:
    """Delete a trace. A project key can delete only its own project's traces
    (another project's is reported as not found); an admin key, any trace."""
    if not TraceRepository(db).delete(trace_id, project_id=project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

