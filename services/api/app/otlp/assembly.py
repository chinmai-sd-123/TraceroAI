"""Collect a run's spans as they arrive, and turn them into a trace when it's done.

Exporters send spans in batches as they end: children first, the root last, a
run spread over several requests. Spans wait in pending_spans until either the
root span (no parent) arrives or the run has been quiet for QUIET_SECONDS; then
the run is built into a trace and its steps, in one transaction, and diagnosed.
A span arriving after that is appended to the finished trace.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import PendingSpanRecord, SpanRecord, TraceRecord
from app.otlp.decode import OtlpSpan
from app.otlp.mapping import span_to_step
from app.otlp.run import build_trace, order_and_root, price_steps
from app.schemas.steps import StepIn
from app.schemas.traces import Trace
from app.schemas.validation import ENVIRONMENT_MAX_LENGTH, PROJECT_ID_MAX_LENGTH
from app.services import deep_eval_queue, fallback_evaluation
from app.services.cost import compute_cost_usd
from app.services.deep_evaluation import initial_deep_status, judge_configured
from app.services.quick_evaluation import run_quick_evaluation
from app.services.steps import step_rows
from app.services.trace_repository import DuplicateTraceError, TraceRepository

logger = logging.getLogger(__name__)

QUIET_SECONDS = 30


@dataclass
class Accepted:
    spans: int = 0
    rejected: int = 0
    finished: list[UUID] = field(default_factory=list)


def project_for(resource: dict[str, Any], key_project: str | None) -> tuple[str, str]:
    """The project and environment a run belongs to. A project key decides the
    project; without one, the resource's traceroai.project_id or service.name."""
    project = key_project or resource.get("traceroai.project_id") or resource.get("service.name") or "default"
    environment = resource.get("deployment.environment.name") or resource.get("deployment.environment") or "dev"
    return str(project)[:PROJECT_ID_MAX_LENGTH], str(environment)[:ENVIRONMENT_MAX_LENGTH]


def accept(db: Session, spans: list[OtlpSpan], *, key_project: str | None) -> Accepted:
    """Stage incoming spans, finish every run whose root arrived, and append
    spans that belong to runs already finished."""
    result = Accepted()
    by_trace: dict[str, list[OtlpSpan]] = defaultdict(list)
    for span in spans:
        by_trace[span.trace_id].append(span)

    for trace_hex, group in by_trace.items():
        trace_id = UUID(trace_hex)
        project, environment = project_for(group[0].resource, key_project)
        steps = [span_to_step(span) for span in group]

        existing = db.get(TraceRecord, trace_id)
        if existing is not None:
            if existing.project_id != project:  # never add to another project's trace
                result.rejected += len(group)
            else:
                _append(db, trace_id, steps)
                result.spans += len(group)
            db.commit()
            continue

        db.execute(
            insert(PendingSpanRecord)
            .values(
                [
                    {
                        "trace_id": trace_id,
                        "span_id": step.step_id,
                        "project_id": project,
                        "environment": environment,
                        "step": step.model_dump(mode="json"),
                        "resource": group[0].resource,
                    }
                    for step in steps
                ]
            )
            .on_conflict_do_nothing()
        )
        db.commit()
        result.spans += len(group)
        if any(span.parent_span_id is None for span in group) and finish(db, trace_id):
            result.finished.append(trace_id)
    return result


def finish(db: Session, trace_id: UUID) -> bool:
    """Build a run's staged spans into a trace. Returns False when there was
    nothing staged, or the trace already existed (the spans are appended)."""
    rows = db.execute(
        delete(PendingSpanRecord)
        .where(PendingSpanRecord.trace_id == trace_id)
        .returning(
            PendingSpanRecord.project_id,
            PendingSpanRecord.environment,
            PendingSpanRecord.step,
            PendingSpanRecord.resource,
        )
    ).all()
    if not rows:
        db.rollback()
        return False

    project, environment, _, resource = rows[0]
    steps = order_and_root([StepIn.model_validate(row.step) for row in rows])
    price_steps(steps)
    trace = _prepare(build_trace(trace_id.hex, steps, project_id=project, environment=environment, resource=resource))

    try:
        # Commits the delete above together with the new trace and its steps.
        TraceRepository(db).save(trace, steps)
    except DuplicateTraceError:
        # Finished by a concurrent request; the rollback put the spans back.
        _append_pending(db, trace_id)
        return False
    _schedule_judge(trace)
    return True


def finish_quiet(db: Session, *, quiet_seconds: int = QUIET_SECONDS, limit: int = 50) -> int:
    """Finish runs whose root span never arrived and that have been quiet for
    quiet_seconds (the database's clock). Returns how many became traces."""
    stale = list(
        db.scalars(
            select(PendingSpanRecord.trace_id)
            .group_by(PendingSpanRecord.trace_id)
            .having(func.max(PendingSpanRecord.received_at) <= func.now() - timedelta(seconds=quiet_seconds))
            .limit(limit)
        ).all()
    )
    db.commit()
    return sum(finish(db, trace_id) for trace_id in stale)


def _prepare(trace: Trace) -> Trace:
    """What ingest does to an SDK trace: price it, run the quick checks."""
    if trace.generation is not None:
        usage = trace.generation.usage
        if usage.total_tokens is None and (usage.prompt_tokens is not None or usage.completion_tokens is not None):
            usage.total_tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)
        if usage.cost_usd is None:
            usage.cost_usd = compute_cost_usd(trace.generation.model, usage)
    trace = run_quick_evaluation(trace, semantic=False)
    trace.evaluations.deep_status = initial_deep_status() if trace.generation is not None else "skipped"
    return trace


def _schedule_judge(trace: Trace) -> None:
    if trace.generation is None or not judge_configured():
        return
    if not deep_eval_queue.enqueue_deep_eval_request(trace.trace_id):
        fallback_evaluation.submit_fallback_evaluation(trace.trace_id)


def _append(db: Session, trace_id: UUID, steps: list[StepIn]) -> None:
    """Add late steps to a finished trace, after the ones it has."""
    last = db.scalar(select(func.max(SpanRecord.position)).where(SpanRecord.trace_id == trace_id))
    rows = step_rows(trace_id, steps)
    for offset, row in enumerate(rows):
        row["position"] = (last if last is not None else -1) + 1 + offset
    db.execute(insert(SpanRecord).values(rows).on_conflict_do_nothing())


def _append_pending(db: Session, trace_id: UUID) -> None:
    rows = db.execute(
        delete(PendingSpanRecord)
        .where(PendingSpanRecord.trace_id == trace_id)
        .returning(PendingSpanRecord.project_id, PendingSpanRecord.step)
    ).all()
    existing = db.get(TraceRecord, trace_id)
    if existing is not None:
        steps = [StepIn.model_validate(row.step) for row in rows if row.project_id == existing.project_id]
        if steps:
            _append(db, trace_id, steps)
    db.commit()
