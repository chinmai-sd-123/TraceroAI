from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.tenancy import ReadScope, read_scope
from app.db.session import get_db
from app.services.trace_query import TraceFilters, recovery_runs

router = APIRouter(prefix="/v1/recovery-runs", tags=["recovery"])


@router.get("")
def list_recovery_runs(
    project_id: str | None = None,
    since: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> list[dict]:
    """RecoveryAgent runs the caller may read, most recently active first.

    Each run lists its attempts' trace ids in order, the lever the agent pulled
    before each attempt (null on the first), the top_k each attempt used, and
    the diagnosis of the first and last attempt."""
    return recovery_runs(
        db,
        TraceFilters(project_ids=scope.narrow(project_id), since=since),
        limit=limit,
    )
