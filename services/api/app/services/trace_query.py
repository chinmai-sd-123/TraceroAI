"""Paginated trace listing and SQL-side summary metrics.

Listing is keyset-paginated on (created_at, trace_id), newest first: a page
costs the same however deep it is, and traces arriving between requests don't
shift later pages. The cursor is opaque to clients.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Float, and_, cast, func, or_, select
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


def encode_cursor(record: TraceRecord) -> str:
    raw = f"{record.created_at.isoformat()}|{record.trace_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        created_at, trace_id = raw.split("|", 1)
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
    return conditions


def list_page(
    db: Session, filters: TraceFilters, *, limit: int, cursor: str | None = None
) -> tuple[list[TraceRecord], str | None]:
    """One page of traces, newest first, and the cursor for the next page (None
    when this is the last)."""
    statement = select(TraceRecord).where(*_where(filters))
    if cursor:
        created_at, trace_id = decode_cursor(cursor)
        statement = statement.where(
            or_(
                TraceRecord.created_at < created_at,
                and_(TraceRecord.created_at == created_at, TraceRecord.trace_id < trace_id),
            )
        )
    statement = statement.order_by(
        TraceRecord.created_at.desc(), TraceRecord.trace_id.desc()
    ).limit(limit + 1)
    records = list(db.scalars(statement).all())
    if len(records) > limit:
        return records[:limit], encode_cursor(records[limit - 1])
    return records, None


def summary(db: Session, filters: TraceFilters) -> dict:
    """Headline numbers over every matching trace, computed in the database."""
    where = _where(filters)
    by_diagnosis = dict(
        db.execute(
            select(TraceRecord.diagnosis_label, func.count())
            .where(*where)
            .group_by(TraceRecord.diagnosis_label)
        ).all()
    )
    source = TraceRecord.payload["diagnosis"]["source"].astext
    by_source = {
        (key or "unknown"): count
        for key, count in db.execute(
            select(source, func.count()).where(*where).group_by(source)
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

    cost_value = cast(TraceRecord.payload["generation"]["usage"]["cost_usd"].astext, Float)
    priced = cost_value > 0
    cost = db.execute(
        select(
            func.count().filter(priced),
            func.sum(cost_value).filter(priced),
        ).where(*where)
    ).one()

    total = sum(by_diagnosis.values())
    healthy = sum(by_diagnosis.get(label, 0) for label in HEALTHY_LABELS)
    return {
        "total": total,
        "healthy": healthy,
        "by_diagnosis": {(k or "pending"): v for k, v in by_diagnosis.items()},
        "by_source": by_source,
        "latency_ms": {
            "measured": latency[0],
            "avg": _round(latency[1]),
            "p50": _round(latency[2]),
            "p95": _round(latency[3]),
        },
        "cost_usd": {
            "priced": cost[0],
            "total": cost[1],
            "avg": (cost[1] / cost[0]) if cost[0] else None,
        },
    }


def _round(value) -> int | None:
    return None if value is None else int(round(float(value)))
