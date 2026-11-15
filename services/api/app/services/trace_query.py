"""Paginated trace listing and SQL-side summary metrics.

Listing is keyset-paginated: newest first on (created_at, trace_id), oldest
first on the same columns ascending, or slowest first on (latency, created_at,
trace_id). A page costs the same however deep it is, and traces arriving
between requests don't shift later pages. The cursor is opaque to clients and
only valid for the sort order that produced it.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import Integer, cast, func, select, tuple_
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session

from app.db.models import TraceRecord

HEALTHY_LABELS = ("healthy_answer", "correct_refusal")


class InvalidCursor(ValueError):
    """The cursor wasn't produced by this API."""


@dataclass(frozen=True)
class TraceFilters:
    project_ids: Collection[str] | None = None  # None = every project
    diagnosis: str | None = None
    model: str | None = None
    environment: str | None = None
    text: str | None = None  # substring of the query, case-insensitive
    since: datetime | None = None
    until: datetime | None = None
    recovery_run_id: str | None = None  # attempts of one RecoveryAgent run


TraceSort = Literal["newest", "oldest", "slowest"]

# Cursor prefixes per sort order. Newest-first cursors keep the original
# unprefixed format, so cursors handed out before sorting existed still work.
_CURSOR_PREFIX: dict[str, str] = {"newest": "", "oldest": "o|", "slowest": "s|"}


def _latency():
    # Unmeasured traces (NULL or 0) sort last when slowest first.
    return func.coalesce(TraceRecord.total_latency_ms, 0)


def encode_cursor(record: TraceRecord, sort: TraceSort = "newest") -> str:
    parts = [record.created_at.isoformat(), str(record.trace_id)]
    if sort == "slowest":
        parts.insert(0, str(record.total_latency_ms or 0))
    raw = (_CURSOR_PREFIX[sort] + "|".join(parts)).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, sort: TraceSort = "newest") -> tuple:
    """The sort key of the last row on the previous page."""
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        prefix = _CURSOR_PREFIX[sort]
        other = [p for s, p in _CURSOR_PREFIX.items() if p and s != sort]
        if not raw.startswith(prefix) or any(raw.startswith(p) for p in other):
            raise ValueError("cursor from another sort order")
        body = raw[len(prefix):]
        if sort == "slowest":
            latency, created_at, trace_id = body.split("|", 2)
            return int(latency), datetime.fromisoformat(created_at), UUID(trace_id)
        created_at, trace_id = body.split("|", 1)
        return datetime.fromisoformat(created_at), UUID(trace_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise InvalidCursor("Invalid cursor.") from exc


def _where(filters: TraceFilters) -> list:
    conditions = []
    if filters.project_ids is not None:
        conditions.append(TraceRecord.project_id.in_(sorted(filters.project_ids)))
    if filters.diagnosis:
        conditions.append(TraceRecord.diagnosis_label == filters.diagnosis)
    if filters.model:
        conditions.append(TraceRecord.model_name == filters.model)
    if filters.environment:
        conditions.append(TraceRecord.environment == filters.environment)
    if filters.text:
        escaped = filters.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(TraceRecord.query_text.ilike(f"%{escaped}%", escape="\\"))
    if filters.since:
        conditions.append(TraceRecord.created_at >= filters.since)
    if filters.until:
        conditions.append(TraceRecord.created_at < filters.until)
    if filters.recovery_run_id:
        conditions.append(_recovery_run_id() == filters.recovery_run_id)
    return conditions


def _recovery_run_id():
    # Set by the SDK's RecoveryAgent on every attempt of a run.
    return TraceRecord.payload["metadata"]["recovery_run_id"].astext


def recovery_runs(db: Session, filters: TraceFilters, *, limit: int) -> list[dict]:
    """RecoveryAgent runs, most recently active first: each run's attempts in
    order with the lever that led to each, and the first and last diagnosis."""
    run_id = _recovery_run_id()
    metadata = TraceRecord.payload["metadata"]
    attempt = cast(metadata["attempt"].astext, Integer)

    def in_order(column):
        return func.array_agg(aggregate_order_by(column, attempt.asc(), TraceRecord.created_at.asc()))

    rows = db.execute(
        select(
            run_id,
            func.count(),
            func.min(TraceRecord.created_at),
            func.max(TraceRecord.created_at),
            in_order(TraceRecord.trace_id),
            in_order(TraceRecord.query_text),
            in_order(TraceRecord.diagnosis_label),
            in_order(metadata["recovery_action"].astext),
            in_order(metadata["top_k"].astext),
        )
        .where(*_where(filters), run_id.is_not(None))
        .group_by(run_id)
        .order_by(func.max(TraceRecord.created_at).desc())
        .limit(limit)
    ).all()
    return [
        {
            "run_id": rid,
            "question": questions[0],
            "attempts": count,
            "trace_ids": [str(t) for t in trace_ids],
            "diagnoses": list(diagnoses),
            "first_diagnosis": diagnoses[0],
            "final_diagnosis": diagnoses[-1],
            "actions": list(actions),
            "top_k": [int(k) if k and k.isdigit() else None for k in top_ks],
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
        }
        for rid, count, started, ended, trace_ids, questions, diagnoses, actions, top_ks in (tuple(r) for r in rows)
    ]


def list_page(
    db: Session,
    filters: TraceFilters,
    *,
    limit: int,
    cursor: str | None = None,
    sort: TraceSort = "newest",
) -> tuple[list[TraceRecord], str | None]:
    """One page of traces in the given order, and the cursor for the next page
    (None when this is the last)."""
    if sort == "slowest":
        key = (_latency(), TraceRecord.created_at, TraceRecord.trace_id)
    else:
        key = (TraceRecord.created_at, TraceRecord.trace_id)
    ascending = sort == "oldest"

    statement = select(TraceRecord).where(*_where(filters))
    if cursor:
        after = decode_cursor(cursor, sort)
        statement = statement.where(tuple_(*key) > after if ascending else tuple_(*key) < after)
    statement = statement.order_by(
        *[column.asc() if ascending else column.desc() for column in key]
    ).limit(limit + 1)
    records = list(db.scalars(statement).all())
    if len(records) > limit:
        return records[:limit], encode_cursor(records[limit - 1], sort)
    return records, None


def summary(db: Session, filters: TraceFilters) -> dict:
    """Headline numbers over every matching trace, computed in the database."""
    where = _where(filters)
    by_diagnosis: dict[str | None, int] = {
        label: count
        for label, count in db.execute(
            select(TraceRecord.diagnosis_label, func.count())
            .where(*where)
            .group_by(TraceRecord.diagnosis_label)
        ).all()
    }
    source = TraceRecord.diagnosis_source
    by_source = {
        (key or "unknown"): count
        for key, count in db.execute(
            select(source, func.count()).where(*where).group_by(source)
        ).all()
    }

    by_model = {
        (model or "unknown"): count
        for model, count in db.execute(
            select(TraceRecord.model_name, func.count()).where(*where).group_by(TraceRecord.model_name)
        ).all()
    }
    by_environment = {
        environment: count
        for environment, count in db.execute(
            select(TraceRecord.environment, func.count()).where(*where).group_by(TraceRecord.environment)
        ).all()
    }

    measured = TraceRecord.total_latency_ms > 0
    latency = db.execute(
        select(
            func.count().filter(measured),
            func.avg(TraceRecord.total_latency_ms).filter(measured),
            func.percentile_cont(0.5)
            .within_group(TraceRecord.total_latency_ms)
            .filter(measured),
            func.percentile_cont(0.95)
            .within_group(TraceRecord.total_latency_ms)
            .filter(measured),
        ).where(*where)
    ).one()

    cost_value = TraceRecord.cost_usd
    priced = cost_value > 0
    cost = db.execute(
        select(
            func.count().filter(priced),
            func.sum(cost_value).filter(priced),
        ).where(*where)
    ).one()

    priced_count, cost_total = cost[0], cost[1]  # the sum is NULL when nothing is priced

    total = sum(by_diagnosis.values())
    healthy = sum(by_diagnosis.get(label, 0) for label in HEALTHY_LABELS)
    return {
        "total": total,
        "healthy": healthy,
        "by_diagnosis": {(k or "pending"): v for k, v in by_diagnosis.items()},
        "by_source": by_source,
        "by_model": by_model,
        "by_environment": by_environment,
        "latency_ms": {
            "measured": latency[0],
            "avg": _round(latency[1]),
            "p50": _round(latency[2]),
            "p95": _round(latency[3]),
        },
        "cost_usd": {
            "priced": priced_count,
            "total": cost_total,
            "avg": (cost_total / priced_count) if priced_count and cost_total is not None else None,
        },
    }


BUCKET_SIZES = {"hour": timedelta(hours=1), "day": timedelta(days=1)}
MAX_BUCKETS = 400


def bucket_starts(since: datetime, until: datetime, bucket: str) -> list[datetime]:
    """Contiguous bucket boundaries covering [since, until), aligned to whole
    UTC hours or days so the same instant always lands in the same bucket."""
    size = BUCKET_SIZES[bucket]
    start = since.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        start = start.replace(hour=0)
    starts = []
    while start < until:
        starts.append(start)
        start += size
    return starts


def timeseries(db: Session, filters: TraceFilters, *, bucket: str, starts: list[datetime]) -> list[dict]:
    """Trace counts and p95 latency per bucket. Empty buckets are included, so
    a chart's time axis has no gaps. Bucketing is done on epoch seconds, which
    keeps it independent of the database session's time zone."""
    if not starts:
        return []
    step = BUCKET_SIZES[bucket].total_seconds()
    origin = starts[0].timestamp()
    index = func.floor((func.extract("epoch", TraceRecord.created_at) - origin) / step)
    measured = TraceRecord.total_latency_ms > 0
    rows = db.execute(
        select(
            index,
            func.count(),
            func.count().filter(TraceRecord.diagnosis_label.in_(HEALTHY_LABELS)),
            func.percentile_cont(0.95).within_group(TraceRecord.total_latency_ms).filter(measured),
        )
        .where(*_where(filters), TraceRecord.created_at >= starts[0])
        .group_by(index)
    ).all()
    by_index = {int(i): (total, healthy, p95) for i, total, healthy, p95 in rows}
    series = []
    for i, start in enumerate(starts):
        total, healthy, p95 = by_index.get(i, (0, 0, None))
        series.append(
            {"start": start.isoformat(), "total": total, "healthy": healthy, "p95_ms": _round(p95)}
        )
    return series


def _round(value) -> int | None:
    return None if value is None else int(round(float(value)))
