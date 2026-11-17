"""Steps: what happened inside a trace, as a tree.

A trace is one run of an application; its steps are the work inside it (a
retrieval, a model call, a tool call, an agent deciding what to do next), each
with a parent, a start and end, and what went in and came out. See
docs/adr/0002-traces-made-of-steps.md.

Kinds follow OpenInference's span kinds, so OpenTelemetry spans map onto them
without translation tables.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

StepKind = Literal["agent", "chain", "llm", "tool", "retriever", "embedding", "reranker", "guardrail"]
StepStatus = Literal["ok", "error", "unset"]

STEP_ID_MAX_LENGTH = 64
STEP_NAME_MAX_LENGTH = 200
# Far above a real agent run; the request body limit is the overall cap on size.
MAX_STEPS_PER_TRACE = 1000


class StepIn(BaseModel):
    """One step as a client sends it."""

    step_id: str = Field(..., min_length=1, max_length=STEP_ID_MAX_LENGTH)
    parent_id: str | None = Field(default=None, max_length=STEP_ID_MAX_LENGTH)
    kind: StepKind
    name: str = Field(..., min_length=1, max_length=STEP_NAME_MAX_LENGTH)
    started_at: datetime
    ended_at: datetime | None = None
    status: StepStatus = "ok"
    status_message: str | None = Field(default=None, max_length=2000)
    input: Any = None
    output: Any = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class Step(StepIn):
    """A stored step, as GET /v1/traces/{id} returns it."""

    duration_ms: int | None = None


def check_step_tree(steps: list[StepIn]) -> None:
    """Raise ValueError unless the steps form a tree (or several): unique ids,
    every parent present, no step its own ancestor, and no step ending before
    it starts."""
    ids: dict[str, StepIn] = {}
    for step in steps:
        if step.step_id in ids:
            raise ValueError(f"step_id {step.step_id!r} is used more than once")
        ids[step.step_id] = step
    for step in steps:
        if step.parent_id is not None and step.parent_id not in ids:
            raise ValueError(f"step {step.step_id!r} has parent {step.parent_id!r}, which isn't in the trace")
        if step.ended_at is not None and step.ended_at < step.started_at:
            raise ValueError(f"step {step.step_id!r} ends before it starts")
    # Walk up from each step; a walk longer than the number of steps is a loop.
    for step in steps:
        seen = 0
        parent = step.parent_id
        while parent is not None:
            seen += 1
            if seen > len(steps):
                raise ValueError(f"step {step.step_id!r} is its own ancestor")
            parent = ids[parent].parent_id
