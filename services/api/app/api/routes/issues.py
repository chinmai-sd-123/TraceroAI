from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.tenancy import ReadScope, read_scope, write_project
from app.db.session import get_db
from app.services.issues import IssueStatus, issue_exists, list_issues, set_resolved

router = APIRouter(prefix="/v1/issues", tags=["issues"])


class IssueRef(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    issue_key: str = Field(min_length=1, max_length=2000)


@router.get("")
def get_issues(
    project_id: str | None = None,
    since: datetime | None = None,
    status: IssueStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    scope: ReadScope = Depends(read_scope),
) -> list[dict]:
    """Failing traces grouped by failure label and the source of the top chunk.

    Regressed issues (failures after being marked resolved) come first, then
    open ones, then resolved ones; within each, most recently seen first."""
    return list_issues(db, project_ids=scope.narrow(project_id), since=since, status=status, limit=limit)


def _change(ref: IssueRef, db: Session, key_project: str | None, *, resolved: bool) -> dict:
    # A project key may change only its own project's issues. Another project's
    # issue is reported as not found, as reads are.
    if (key_project is not None and key_project != ref.project_id) or not issue_exists(
        db, ref.project_id, ref.issue_key
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")
    set_resolved(db, ref.project_id, ref.issue_key, resolved=resolved)
    return {"project_id": ref.project_id, "issue_key": ref.issue_key, "resolved": resolved}


@router.post("/resolve")
def resolve_issue(
    ref: IssueRef, db: Session = Depends(get_db), key_project: str | None = Depends(write_project)
) -> dict:
    """Mark an issue resolved. Failures after this make it regressed."""
    return _change(ref, db, key_project, resolved=True)


@router.post("/reopen")
def reopen_issue(
    ref: IssueRef, db: Session = Depends(get_db), key_project: str | None = Depends(write_project)
) -> dict:
    """Mark an issue open again."""
    return _change(ref, db, key_project, resolved=False)
