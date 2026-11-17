"""Issues: failing traces grouped by what failed and where.

An issue key is a failure label plus what that kind of failure usually comes
down to, computed by Postgres (TraceRecord.issue_key, migrations 0006 and 0007):
the top retrieved source for retrieval failures, the prompt version for
grounding and answer failures. Counts and dates come straight from the traces,
so they can't drift. The only stored state is when someone marked an issue
resolved; an issue that failed again after that has regressed.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Literal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import aggregate_order_by, insert
from sqlalchemy.orm import Session

from app.db.models import IssueStateRecord, TraceRecord

# Diagnoses that make a trace part of an issue. Must match ISSUE_KEY_SQL.
FAILURE_LABELS = ("retrieval_miss", "low_context_relevance", "unsupported_claim", "wrong_answer", "needs_review")

IssueStatus = Literal["open", "regressed", "resolved"]

# What the second part of an issue key is, by label. Must match ISSUE_KEY_SQL.
GROUPED_BY_PROMPT = ("unsupported_claim", "wrong_answer")


def split_key(issue_key: str) -> tuple[str, str]:
    """(label, source or prompt version) from an issue key."""
    label, _, source = issue_key.partition("|")
    return label, source


def grouped_by(label: str) -> Literal["prompt_version", "top_source"]:
    return "prompt_version" if label in GROUPED_BY_PROMPT else "top_source"


def status_of(resolved_at: datetime | None, last_seen: datetime) -> IssueStatus:
    if resolved_at is None:
        return "open"
    return "regressed" if last_seen > resolved_at else "resolved"


def list_issues(
    db: Session,
    *,
    project_ids: Collection[str] | None,
    since: datetime | None = None,
    status: IssueStatus | None = None,
    limit: int = 50,
) -> list[dict]:
    """Issues with at least one failing trace in range, most recently seen first.

    Open and regressed issues come before resolved ones."""
    state = IssueStateRecord
    where: list[ColumnElement[bool]] = [TraceRecord.issue_key.is_not(None)]
    if project_ids is not None:
        where.append(TraceRecord.project_id.in_(sorted(project_ids)))
    if since is not None:
        where.append(TraceRecord.created_at >= since)

    newest_first = TraceRecord.created_at.desc()
    rows = db.execute(
        select(
            TraceRecord.project_id.label("project_id"),
            TraceRecord.issue_key.label("issue_key"),
            func.count().label("count"),
            func.count(func.distinct(TraceRecord.query_text)).label("questions"),
            func.min(TraceRecord.created_at).label("first_seen"),
            func.max(TraceRecord.created_at).label("last_seen"),
            func.array_agg(aggregate_order_by(TraceRecord.trace_id, newest_first)).label("trace_ids"),
            func.array_agg(aggregate_order_by(TraceRecord.query_text, newest_first)).label("texts"),
            state.resolved_at.label("resolved_at"),
            func.count()
            .filter(state.resolved_at.is_not(None), TraceRecord.created_at > state.resolved_at)
            .label("since_resolved"),
        )
        .outerjoin(
            state,
            (state.project_id == TraceRecord.project_id) & (state.issue_key == TraceRecord.issue_key),
        )
        .where(*where)
        .group_by(TraceRecord.project_id, TraceRecord.issue_key, state.resolved_at)
    ).all()

    issues = []
    for row in rows:
        # Named columns, typed here: the row's own types are too broad to check.
        m = row._mapping
        key: str = m["issue_key"]
        first_seen: datetime = m["first_seen"]
        last_seen: datetime = m["last_seen"]
        resolved_at: datetime | None = m["resolved_at"]
        trace_ids: list = m["trace_ids"]
        texts: list[str] = m["texts"]
        label, source = split_key(key)
        current = status_of(resolved_at, last_seen)
        if status is not None and current != status:
            continue
        distinct_recent: list[str] = []
        for text in texts:
            if text not in distinct_recent:
                distinct_recent.append(text)
            if len(distinct_recent) == 3:
                break
        issues.append(
            {
                "project_id": m["project_id"],
                "issue_key": key,
                "label": label,
                "source": source,
                "grouped_by": grouped_by(label),
                "status": current,
                "count": m["count"],
                "questions": m["questions"],
                "first_seen": first_seen.isoformat(),
                "last_seen": last_seen.isoformat(),
                "resolved_at": resolved_at.isoformat() if resolved_at else None,
                "count_since_resolved": m["since_resolved"],
                "latest_trace_id": str(trace_ids[0]),
                "recent_questions": distinct_recent,
            }
        )
    rank = {"regressed": 0, "open": 1, "resolved": 2}
    issues.sort(key=lambda i: (rank[i["status"]], -datetime.fromisoformat(i["last_seen"]).timestamp()))
    return issues[:limit]


def issue_exists(db: Session, project_id: str, issue_key: str) -> bool:
    return (
        db.execute(
            select(TraceRecord.trace_id)
            .where(TraceRecord.project_id == project_id, TraceRecord.issue_key == issue_key)
            .limit(1)
        ).first()
        is not None
    )


def set_resolved(db: Session, project_id: str, issue_key: str, *, resolved: bool) -> None:
    """Mark an issue resolved (now) or open again.

    "Now" is the database's clock, the one that stamps traces' created_at: an
    issue regresses when a trace arrives after it was resolved, and comparing
    times from two machines' clocks would miss regressions when they drift."""
    at = func.now() if resolved else None
    db.execute(
        insert(IssueStateRecord)
        .values(project_id=project_id, issue_key=issue_key, resolved_at=at, updated_at=func.now())
        .on_conflict_do_update(
            index_elements=[IssueStateRecord.project_id, IssueStateRecord.issue_key],
            set_={"resolved_at": at, "updated_at": func.now()},
        )
    )
    db.commit()
