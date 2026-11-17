from datetime import datetime, UTC
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.schemas.steps import MAX_STEPS_PER_TRACE, Step, StepIn, check_step_tree
from app.schemas.validation import (
    ENVIRONMENT_MAX_LENGTH,
    MAX_CHUNKS_PER_TRACE,
    MODEL_MAX_LENGTH,
    PROJECT_ID_MAX_LENGTH,
    STATUS_MAX_LENGTH,
    VERSION_MAX_LENGTH,
    strip_nul,
)

class ProjectInfo(BaseModel):
    project_id: str = Field(default="demo-rag", min_length=1, max_length=PROJECT_ID_MAX_LENGTH)
    environment: str = Field(default="dev", min_length=1, max_length=ENVIRONMENT_MAX_LENGTH)

class QueryTrace(BaseModel):
    original: str= Field(..., min_length=1)
    rewritten: str | None = None
    rewrite_changed: bool = False
    rewrite_method: str | None = None
    rewrite_version: str | None = None

class RetrievalConfig(BaseModel):
    lexical_top_k: int | None = None
    dense_top_k: int | None = None
    final_top_k: int | None = None
    fusion: str | None = None
    reranker: str | None = None

class RetrievedChunk(BaseModel):
    rank: int = Field(..., ge=1)
    chunk_id: str = Field(..., min_length=1)
    document_id: str | None = None
    document_title: str | None = None
    section: str | None = None
    source: str | None = None

    base_score: float | None = None
    final_score: float | None = None
    rrf_score: float | None = None
    lexical_rank: int | None = None
    dense_rank: int | None = None
    lexical_score: float | None = None
    dense_score: float | None = None

    text: str = Field(..., min_length=1)
    text_preview: str | None = None

class RetrievalTrace(BaseModel):
    strategy: str = Field(default="vector", min_length=1)
    config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    chunks: list[RetrievedChunk] = Field(default_factory=list, max_length=MAX_CHUNKS_PER_TRACE)


class PromptTrace(BaseModel):
    version: str | None = None
    template_name: str | None= None
    content: str | None = None

class UsageTrace(BaseModel):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    # cost_usd is computed server-side from a price table (the SDK sends tokens,
    # the server owns pricing), but is accepted if a client provides it.
    cost_usd: float | None = Field(default=None, ge=0)


class GenerationTrace(BaseModel):
    provider: str | None= None
    model: str = Field(..., min_length=1, max_length=MODEL_MAX_LENGTH)
    temperature: float | None= None
    # Any other tunable generation parameters (top_p, max_tokens, seed,
    # frequency_penalty, presence_penalty, ...). Kept as a free-form dict so new
    # knobs don't require a schema change, and experiments can compare on them.
    parameters: dict[str, Any] = Field(default_factory=dict)
    answer: str= Field(..., min_length=1)
    answered: bool= True
    usage: UsageTrace = Field(default_factory=UsageTrace)

class LatencyTrace(BaseModel):
    retrieval_ms: int | None= Field(default=None, ge=0)
    prompt_build_ms: int | None= Field(default=None, ge=0)
    generation_ms: int | None= Field(default=None, ge=0)
    total_ms:int | None= Field(default=None, ge=0)

# Which evaluation produced a diagnosis, from least to most reliable:
#   lexical    term overlap only (what ingest computes, no network)
#   embedding  semantic similarity (the background pass, when embeddings work)
#   judge      the LLM judge
DiagnosisSource = Literal["lexical", "embedding", "judge"]

# State of the LLM-judge evaluation for a trace:
#   pending   queued or running
#   complete  judge results stored
#   partial   some judge calls failed; the diagnosis uses the ones that worked
#   failed    every judge call failed; the diagnosis comes from the quick checks
#   skipped   no judge configured (or deep evaluation disabled)
DeepEvaluationStatus = Literal["pending", "complete", "partial", "failed", "skipped"]


class DiagnosisTrace(BaseModel):
    label: str= Field(default= "pending", min_length=1)
    reason:str | None= None
    # None on traces stored before sources were recorded.
    source: DiagnosisSource | None = None


class FeedbackEntry(BaseModel):
    rating: Literal["thumbs_up", "thumbs_down"]
    comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FeedbackRequest(BaseModel):
    """What a client may send. The timestamp is server-owned, and the comment is
    capped because the endpoint is reachable without a key."""

    rating: Literal["thumbs_up", "thumbs_down"]
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="before")
    @classmethod
    def _strip_nul(cls, data: Any) -> Any:
        return strip_nul(data)

class EvaluationResult(BaseModel):
    evaluator_name: str
    evaluator_version: str | None = None
    label: str
    score: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

class EvaluationsTrace(BaseModel):
    quick: list[EvaluationResult] = Field(default_factory=list)
    deep: list[EvaluationResult] = Field(default_factory=list)
    # None on traces stored before the status was recorded.
    deep_status: DeepEvaluationStatus | None = None

# A trace that isn't a RAG run (an agent, say, arriving over OpenTelemetry) has
# no retrieval-and-answer shape for the checks to work on, so it isn't diagnosed:
# its diagnosis says so instead of guessing. Agent diagnosis is planned.
NOT_DIAGNOSED = "not_diagnosed"


class _RunFields(BaseModel):
    """What every trace has, however it arrived."""

    schema_version: str = Field(default="tracero_trace_v1", max_length=VERSION_MAX_LENGTH)
    trace_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = Field(default="answered", min_length=1, max_length=STATUS_MAX_LENGTH)

    project: ProjectInfo = Field(default_factory=ProjectInfo)
    query: QueryTrace
    prompt: PromptTrace = Field(default_factory=PromptTrace)
    latency: LatencyTrace = Field(default_factory=LatencyTrace)

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _strip_nul(cls, data: Any) -> Any:
        return strip_nul(data)


class TraceIngestRequest(_RunFields):
    """What a client sends to POST /v1/traces.

    Evaluations, diagnosis and feedback are not part of it: the server computes
    the first two and feedback has its own endpoint. If a client sends them anyway
    they are ignored, so older SDKs that still include them keep working.

    trace_id may be set by the client. Sending the same id again returns the
    stored trace instead of creating a second one, which makes retries safe.
    """

    retrieval: RetrievalTrace
    generation: GenerationTrace

    # The steps inside the run, as a tree (agents, tool calls, nested model
    # calls). Optional: without them the server derives steps from the fields
    # above. Stored in their own table, not in the trace document, so they're
    # excluded from dumps; GET /v1/traces/{id} returns them (TraceDetail).
    steps: list[StepIn] | None = Field(default=None, max_length=MAX_STEPS_PER_TRACE, exclude=True)

    @model_validator(mode="after")
    def _steps_form_a_tree(self) -> "TraceIngestRequest":
        if self.steps:
            check_step_tree(self.steps)
        return self


class Trace(_RunFields):
    """A stored trace: what the client sent plus what the server adds to it.

    generation is None for a run with no single model answer to check (an
    agent run from OpenTelemetry, say); such a trace is NOT_DIAGNOSED."""

    retrieval: RetrievalTrace = Field(default_factory=RetrievalTrace)
    generation: GenerationTrace | None = None
    evaluations: EvaluationsTrace = Field(default_factory=EvaluationsTrace)
    diagnosis: DiagnosisTrace = Field(default_factory=DiagnosisTrace)
    feedback: list[FeedbackEntry] = Field(default_factory=list)

    @property
    def is_rag(self) -> bool:
        """Whether the RAG checks apply: a model answer to check against context."""
        return self.generation is not None


def rag_generation(trace: Trace) -> GenerationTrace:
    """The answer of a RAG trace, for code that only runs on RAG traces (the
    evaluators). Raises ValueError for any other trace."""
    if trace.generation is None:
        raise ValueError(f"trace {trace.trace_id} is not a RAG run: it has no model answer to check")
    return trace.generation


class TraceDetail(Trace):
    """One trace with its steps, as GET /v1/traces/{id} returns it."""

    steps: list[Step] = Field(default_factory=list)  # type: ignore[assignment]


class TraceIngestResponse(BaseModel):
    trace_id: UUID
    status: str
    message: str
    # Present when the caller requested synchronous deep eval (e.g. the recovery
    # agent): the judge-corrected diagnosis, available immediately in the response
    # so the caller doesn't have to poll for the async deep eval to land.
    diagnosis: DiagnosisTrace | None = None

