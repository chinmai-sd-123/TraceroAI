"""Alerts: tell a webhook when something needs a person.

Three alerts, checked by the worker every minute:

- a new issue: a kind of failure not seen before in a project. Issues that
  already existed when alerts were first checked are recorded as known, not
  announced, so turning alerts on doesn't flood the channel;
- a regressed issue: one marked resolved has failed again (announced once
  per resolution);
- a project's failure rate over the last alert_window_minutes crossing
  alert_failure_rate, once it has at least alert_min_runs diagnosed runs; and
  again when it drops back below, rather than every minute in between.

The webhook gets {"text": ..., "event": {...}}: "text" is what Slack-compatible
incoming webhooks post, "event" the same alert as data. An alert counts as sent
only when the webhook accepts it, so one that fails is retried next check.
Alerts carry the question, label and project, never retrieved text or answers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from sqlalchemy import ColumnElement, and_, exists, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AlertStateRecord, IssueStateRecord, TraceRecord
from app.schemas.traces import NOT_DIAGNOSED
from app.services.issues import FAILURE_LABELS, grouped_by, split_key

logger = logging.getLogger(__name__)

AlertKind = Literal["new_issue", "regressed_issue", "failure_rate", "failure_rate_recovered"]

# One worker at a time checks alerts, so two replicas can't both send one.
_LOCK_ID = 7_341_902_118
# Traces committed a little after their created_at still count as recent.
_LOOKBACK = timedelta(minutes=10)
_ALL = "*"

LABEL_NAMES = {
    "retrieval_miss": "Retrieval miss",
    "low_context_relevance": "Low context relevance",
    "unsupported_claim": "Unsupported claim",
    "wrong_answer": "Wrong answer",
    "needs_review": "Needs review",
}


@dataclass
class Alert:
    kind: AlertKind
    project_id: str
    subject: str  # the issue key, or "failure_rate"
    text: str
    event: dict[str, Any] = field(default_factory=dict)


def check(db: Session, settings: Settings, *, http: httpx.Client | None = None) -> int:
    """Send the alerts that are due. Returns how many were sent."""
    if not settings.alert_webhook_url:
        return 0
    if not db.execute(select(func.pg_try_advisory_xact_lock(_LOCK_ID))).scalar():
        return 0  # another worker is checking
    started = _started_at(db)
    now: datetime = db.execute(select(func.now())).scalar_one()
    # Failures since the last check (or a little before, for late commits), so
    # a worker that was down still announces what happened meanwhile.
    last_checked = db.execute(
        select(AlertStateRecord.sent_at).where(AlertStateRecord.project_id == _ALL, AlertStateRecord.kind == "checked")
    ).scalar()
    since = min(last_checked or now, now) - _LOOKBACK
    _mark(db, "checked")

    due = [
        *_new_issues(db, settings, started, since),
        *_regressed_issues(db, settings),
        *_failure_rates(db, settings, now),
    ]
    db.commit()  # the "known" issues recorded above, and the lock

    sent = 0
    client = http or httpx.Client(timeout=5.0)
    try:
        for alert in due:
            if _deliver(client, settings.alert_webhook_url, alert):
                _record(db, alert)
                db.commit()
                sent += 1
    finally:
        if http is None:
            client.close()
    return sent


def _started_at(db: Session) -> datetime:
    """When alerts were first checked (recorded on the first check)."""
    db.execute(
        insert(AlertStateRecord)
        .values(project_id=_ALL, kind="started", subject=_ALL, state="on")
        .on_conflict_do_nothing()
    )
    return db.execute(
        select(AlertStateRecord.sent_at).where(
            AlertStateRecord.project_id == _ALL, AlertStateRecord.kind == "started"
        )
    ).scalar_one()


def _mark(db: Session, kind: str) -> None:
    db.execute(
        insert(AlertStateRecord)
        .values(project_id=_ALL, kind=kind, subject=_ALL, state="on")
        .on_conflict_do_update(index_elements=["project_id", "kind", "subject"], set_={"sent_at": text("now()")})
    )


def _new_issues(db: Session, settings: Settings, started: datetime, since: datetime) -> list[Alert]:
    known = AlertStateRecord
    recent = (
        select(TraceRecord.project_id, TraceRecord.issue_key)
        .where(
            TraceRecord.issue_key.is_not(None),
            TraceRecord.created_at >= since,
            ~exists().where(
                known.project_id == TraceRecord.project_id,
                known.kind == "new_issue",
                known.subject == TraceRecord.issue_key,
            ),
        )
        .distinct()
    )
    alerts = []
    for row in db.execute(recent).all():
        # Named columns, typed here: the row's own types are too broad to check.
        project_id: str = row._mapping["project_id"]
        issue_key: str = row._mapping["issue_key"]
        first_seen, total, question = _issue_facts(db, project_id, issue_key)
        if first_seen <= started:
            # Existed before alerts were turned on: remember it, don't announce it.
            _record(db, Alert("new_issue", project_id, issue_key, ""), state="known")
            continue
        label, source = split_key(issue_key)
        alerts.append(
            Alert(
                "new_issue",
                project_id,
                issue_key,
                f"New issue in {project_id}: {_describe(label, source)}. "
                f"{_runs(total)} so far, latest: “{_short(question)}”{_link(settings, project_id)}",
                {"label": label, "grouped_by": grouped_by(label), "source": source, "count": total},
            )
        )
    return alerts


def _regressed_issues(db: Session, settings: Settings) -> list[Alert]:
    state = IssueStateRecord
    announced = AlertStateRecord
    rows = db.execute(
        select(state.project_id, state.issue_key, state.resolved_at).where(
            state.resolved_at.is_not(None),
            exists().where(
                TraceRecord.project_id == state.project_id,
                TraceRecord.issue_key == state.issue_key,
                TraceRecord.created_at > state.resolved_at,
            ),
            ~exists().where(
                announced.project_id == state.project_id,
                announced.kind == "regressed_issue",
                announced.subject == state.issue_key,
                announced.sent_at >= state.resolved_at,
            ),
        )
    ).all()
    alerts = []
    for row in rows:
        project_id: str = row._mapping["project_id"]
        issue_key: str = row._mapping["issue_key"]
        resolved_at: datetime = row._mapping["resolved_at"]
        since = db.execute(
            select(func.count()).where(
                TraceRecord.project_id == project_id,
                TraceRecord.issue_key == issue_key,
                TraceRecord.created_at > resolved_at,
            )
        ).scalar_one()
        label, source = split_key(issue_key)
        alerts.append(
            Alert(
                "regressed_issue",
                project_id,
                issue_key,
                f"Regressed in {project_id}: {_describe(label, source)} failed again after it was marked "
                f"resolved ({_runs(since)} since){_link(settings, project_id)}",
                {"label": label, "source": source, "count_since_resolved": since, "resolved_at": resolved_at.isoformat()},
            )
        )
    return alerts


def _failure_rates(db: Session, settings: Settings, now: datetime) -> list[Alert]:
    label = TraceRecord.diagnosis_label
    diagnosed: ColumnElement[bool] = and_(label.is_not(None), label != NOT_DIAGNOSED)
    rows = db.execute(
        select(
            TraceRecord.project_id,
            func.count().filter(diagnosed),
            func.count().filter(label.in_(FAILURE_LABELS)),
        )
        .where(TraceRecord.created_at >= now - timedelta(minutes=settings.alert_window_minutes))
        .group_by(TraceRecord.project_id)
    ).all()
    firing = set(
        db.scalars(
            select(AlertStateRecord.project_id).where(
                AlertStateRecord.kind == "failure_rate", AlertStateRecord.state == "firing"
            )
        ).all()
    )
    window = _minutes(settings.alert_window_minutes)
    alerts = []
    seen = set()
    for project_id, runs, failing in rows:
        seen.add(project_id)
        if runs < settings.alert_min_runs:
            continue
        rate = failing / runs
        event = {"failure_rate": round(rate, 4), "runs": runs, "failing": failing, "window_minutes": settings.alert_window_minutes}
        if rate >= settings.alert_failure_rate and project_id not in firing:
            alerts.append(
                Alert(
                    "failure_rate",
                    project_id,
                    "failure_rate",
                    f"{project_id}: {rate:.0%} of answers failed in the last {window} "
                    f"({failing} of {runs} diagnosed runs; alert at {settings.alert_failure_rate:.0%})"
                    f"{_link(settings, project_id)}",
                    event,
                )
            )
        elif rate < settings.alert_failure_rate and project_id in firing:
            alerts.append(
                Alert(
                    "failure_rate_recovered",
                    project_id,
                    "failure_rate",
                    f"{project_id} recovered: {rate:.0%} of answers failed in the last {window} "
                    f"({failing} of {runs} diagnosed runs)",
                    event,
                )
            )
    # A project with no runs in the window at all has recovered too, quietly:
    # there's nothing to report, but the next spike should alert again.
    for project_id in firing - seen:
        _record(db, Alert("failure_rate_recovered", project_id, "failure_rate", ""), state="ok")
    return alerts


def _deliver(client: httpx.Client, url: str, alert: Alert) -> bool:
    payload = {"text": alert.text, "event": {"kind": alert.kind, "project_id": alert.project_id, **alert.event}}
    try:
        response = client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("Alert not sent (%s); retrying next check: %s", type(exc).__name__, alert.text)
        return False
    if response.status_code >= 300:
        logger.warning("Alert not sent (HTTP %d); retrying next check: %s", response.status_code, alert.text)
        return False
    return True


def _record(db: Session, alert: Alert, *, state: str | None = None) -> None:
    kind = "failure_rate" if alert.kind == "failure_rate_recovered" else alert.kind
    value = state or ("ok" if alert.kind == "failure_rate_recovered" else "firing" if alert.kind == "failure_rate" else "sent")
    db.execute(
        insert(AlertStateRecord)
        .values(project_id=alert.project_id, kind=kind, subject=alert.subject, state=value)
        .on_conflict_do_update(
            index_elements=["project_id", "kind", "subject"], set_={"state": value, "sent_at": text("now()")}
        )
    )


def _issue_facts(db: Session, project_id: str, issue_key: str) -> tuple[datetime, int, str]:
    """An issue's first failure, its count, and its latest question."""
    in_issue = (TraceRecord.project_id == project_id, TraceRecord.issue_key == issue_key)
    first_seen, total = db.execute(select(func.min(TraceRecord.created_at), func.count()).where(*in_issue)).one()
    question = db.execute(
        select(TraceRecord.query_text).where(*in_issue).order_by(TraceRecord.created_at.desc()).limit(1)
    ).scalar_one()
    return first_seen, total, question


def _describe(label: str, source: str) -> str:
    name = LABEL_NAMES.get(label, label)
    if not source:
        return name
    where = "prompt version" if grouped_by(label) == "prompt_version" else "top source"
    return f"{name}, {where} {source}"


def _runs(count: int) -> str:
    return f"{count} failing run{'' if count == 1 else 's'}"


def _minutes(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return "hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minutes"


def _short(question: str, limit: int = 120) -> str:
    question = " ".join(question.split())
    return question if len(question) <= limit else question[: limit - 1] + "…"


def _link(settings: Settings, project_id: str) -> str:
    if not settings.dashboard_url:
        return ""
    query = urlencode({"project": project_id})
    return f"\n{settings.dashboard_url.rstrip('/')}/dashboard/issues?{query}"
