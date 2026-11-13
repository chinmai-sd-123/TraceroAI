from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.tenancy import ReadScope, read_scope
from app.db.session import get_db
from app.services.trace_query import TraceFilters, summary

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
