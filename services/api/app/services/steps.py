"""Turning traces into steps, and steps into rows (docs/adr/0002).

A client can send a trace's steps itself. Every SDK so far sends a flat RAG
trace instead (a query, retrieved chunks, a prompt, one answer), and for those
the steps are derived here: the run, then retrieval, prompt building and
generation, timed from the latencies the client measured.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.db.models import SpanRecord
from app.schemas.steps import Step, StepIn
from app.schemas.traces import Trace


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _after(start: datetime, ms: int | None) -> datetime | None:
    return start + timedelta(milliseconds=ms) if ms is not None else None


def derive_steps(trace: Trace) -> list[StepIn]:
    """The steps of a flat RAG trace. Inputs and outputs are kept small (ids, not
    chunk text): the trace document already holds the full content."""
    start = _aware(trace.timestamp)
    latency = trace.latency
    retrieval = trace.retrieval
    generation = trace.generation
    prompt = trace.prompt

    steps = [
        StepIn(
            step_id="run",
            kind="chain",
            name="RAG pipeline",
            started_at=start,
            ended_at=_after(start, latency.total_ms),
            input={"query": trace.query.original},
            output={"answer": generation.answer} if generation else None,
        )
    ]

    at = start
    ended = _after(at, latency.retrieval_ms)
    steps.append(
        StepIn(
            step_id="retrieval",
            parent_id="run",
            kind="retriever",
            name="retrieve",
            started_at=at,
            ended_at=ended,
            input={"query": trace.query.rewritten or trace.query.original},
            output={"chunk_ids": [chunk.chunk_id for chunk in retrieval.chunks]},
            attributes=_without_none(
                {
                    "strategy": retrieval.strategy,
                    "top_k": retrieval.config.final_top_k,
                    "chunks": len(retrieval.chunks),
                }
            ),
        )
    )
    at = ended or at

    if prompt.version or prompt.template_name or prompt.content or latency.prompt_build_ms is not None:
        ended = _after(at, latency.prompt_build_ms)
        steps.append(
            StepIn(
                step_id="prompt",
                parent_id="run",
                kind="chain",
                name="build prompt",
                started_at=at,
                ended_at=ended,
                attributes=_without_none({"version": prompt.version, "template_name": prompt.template_name}),
            )
        )
        at = ended or at

    if generation is None:  # not a RAG run: no model step to derive
        return steps
    usage = generation.usage
    steps.append(
        StepIn(
            step_id="generation",
            parent_id="run",
            kind="llm",
            name=generation.model,
            started_at=at,
            ended_at=_after(at, latency.generation_ms),
            output={"answered": generation.answered},
            attributes=_without_none(
                {
                    "provider": generation.provider,
                    "model": generation.model,
                    "temperature": generation.temperature,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "cost_usd": usage.cost_usd,
                }
            ),
        )
    )
    return steps


def step_rows(trace_id: UUID, steps: list[StepIn]) -> list[dict[str, Any]]:
    """Rows for the spans table, in the order the steps came."""
    return [
        {
            "trace_id": trace_id,
            "span_id": step.step_id,
            "parent_span_id": step.parent_id,
            "position": position,
            "kind": step.kind,
            "name": step.name,
            "status": step.status,
            "status_message": step.status_message,
            "started_at": _aware(step.started_at),
            "ended_at": _aware(step.ended_at) if step.ended_at else None,
            "input": step.input,
            "output": step.output,
            "attributes": step.attributes,
        }
        for position, step in enumerate(steps)
    ]


def _duration_ms(started_at: datetime, ended_at: datetime | None) -> int | None:
    if ended_at is None:
        return None
    return round((_aware(ended_at) - _aware(started_at)).total_seconds() * 1000)


def as_step(step: StepIn) -> Step:
    """A step that was derived rather than stored, in the response shape."""
    return Step(**step.model_dump(), duration_ms=_duration_ms(step.started_at, step.ended_at))


def to_step(record: SpanRecord) -> Step:
    return Step(
        step_id=record.span_id,
        parent_id=record.parent_span_id,
        kind=record.kind,  # type: ignore[arg-type]  # stored from a validated StepKind
        name=record.name,
        started_at=record.started_at,
        ended_at=record.ended_at,
        status=record.status,  # type: ignore[arg-type]  # stored from a validated StepStatus
        status_message=record.status_message,
        input=record.input,
        output=record.output,
        attributes=record.attributes,
        duration_ms=_duration_ms(record.started_at, record.ended_at),
    )


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}
