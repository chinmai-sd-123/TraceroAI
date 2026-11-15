from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.tenancy import ReadScope, read_scope
from app.db.session import get_db
from app.services.trace_query import MAX_BUCKETS, TraceFilters, bucket_starts, summary, timeseries

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])


@router.get("/summary")
def trace_summary(
    project_id: str | None = None,
    model: str | None = None,
    environment: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> dict:
    """Counts by diagnosis and by diagnosis source, latency percentiles and
    cost, over every trace the caller may read (narrowed by the filters)."""
    return summary(
        db,
        TraceFilters(
            project_ids=scope.narrow(project_id),
            model=model,
            environment=environment,
            since=since,
            until=until,
        ),
    )


@router.get("/timeseries")
def trace_timeseries(
    project_id: str | None = None,
    model: str | None = None,
    environment: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    bucket: Literal["hour", "day"] | None = None,
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> dict:
    """Traces, healthy traces and p95 latency per hour or day. Defaults to
    the last seven days; the bucket defaults to hours for spans up to two
    days and days beyond that."""
    until = _utc(until) if until else datetime.now(UTC)
    since = _utc(since) if since else until - timedelta(days=7)
    if since >= until:
        raise HTTPException(status_code=422, detail="since must be before until.")
    bucket = bucket or ("hour" if until - since <= timedelta(days=2) else "day")
    starts = bucket_starts(since, until, bucket)
    if len(starts) > MAX_BUCKETS:
        raise HTTPException(
            status_code=422,
            detail=f"That range has more than {MAX_BUCKETS} {bucket} buckets; use a larger bucket.",
        )
    filters = TraceFilters(
        project_ids=scope.narrow(project_id),
        model=model,
        environment=environment,
        until=until,
    )
    return {"bucket": bucket, "buckets": timeseries(db, filters, bucket=bucket, starts=starts)}


def _utc(value: datetime) -> datetime:
    # A timestamp without an offset is taken as UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
