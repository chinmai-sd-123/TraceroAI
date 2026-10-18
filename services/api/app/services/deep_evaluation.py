from uuid import UUID

import openai

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.evaluators.deep_groundedness import evaluate_deep_groundedness
from app.evaluators.deep_relevance import (
    evaluate_deep_answer_relevance,
    evaluate_deep_context_relevance,
)
from app.evaluators.diagnosis import diagnose_from_deep, is_refusal
from app.schemas.traces import DiagnosisTrace, EvaluationResult, TraceIngestRequest
from app.services.embeddings import EmbeddingClient
from app.services.llm_judge import LLMJudge, OpenAIJudge
from app.services.quick_evaluation import run_quick_evaluation
from app.services.trace_repository import TraceRepository


DEEP_EVALUATORS = (
    evaluate_deep_context_relevance,
    evaluate_deep_groundedness,
    evaluate_deep_answer_relevance,
)
ERROR_EVALUATOR_NAME = "deep_evaluation"
ERROR_EVALUATOR_VERSION = "llm_judge_openai_v1"

# Provider failures that are worth retrying later: rate limits (by far the most
# common in practice), timeouts, connection drops, and provider 5xx.
# APITimeoutError is a subclass of APIConnectionError.
TRANSIENT_JUDGE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


class TransientEvaluationError(Exception):
    """The judge hit a temporary provider error; nothing was written, retry later."""


def run_deep_evaluation(
    trace_id: UUID,
    judge: LLMJudge | None = None,
    embedder: EmbeddingClient | None = None,
    *,
    retry_transient: bool = False,
) -> None:
    """Everything that evaluates a stored trace off the ingest path (run by the
    worker, or BackgroundTasks when there's no Redis):

    1. Semantic quick eval — the quick evaluators re-run with embeddings. Ingest
       only does the lexical pass, so POST /v1/traces never waits on an
       embeddings API.
    2. Deep eval — the LLM judge. Its diagnosis wins when it's usable.

    Both results are written in a single update.

    retry_transient=True (the worker, before its last attempt) raises
    TransientEvaluationError on a rate limit / timeout instead of recording an
    error result, so the job can be retried. Otherwise any judge failure is
    recorded as an "error" deep result (fail-open).
    """
    settings = get_settings()
    semantic = embedder is not None or bool(settings.openai_api_key)
    if not (semantic or settings.deep_eval_enabled):
        return

    db = SessionLocal()
    try:
        repository = TraceRepository(db)
        record = repository.get(trace_id)
        if record is None:
            return

        trace = TraceIngestRequest(**record.payload)

        quick: list[EvaluationResult] | None = None
        diagnosis: DiagnosisTrace | None = None
        if semantic:
            refreshed = run_quick_evaluation(
                trace.model_copy(deep=True), semantic=True, embedder=embedder
            )
            quick = refreshed.evaluations.quick
            diagnosis = refreshed.diagnosis

        deep: list[EvaluationResult] | None = None
        if settings.deep_eval_enabled:
            deep = _evaluate(trace, judge, settings, retry_transient=retry_transient)
            # Re-diagnose from the judge's verdict — it's more reliable than the
            # quick eval. If the judge errored or yielded nothing usable,
            # diagnose_from_deep returns None and the quick diagnosis stands.
            refused = not trace.generation.answered or is_refusal(trace.generation.answer)
            deep_diagnosis = diagnose_from_deep(deep, refused=refused)
            if deep_diagnosis is not None:
                diagnosis = deep_diagnosis

        repository.set_evaluations(trace_id, quick=quick, deep=deep, diagnosis=diagnosis)
    finally:
        db.close()


def _evaluate(
    trace: TraceIngestRequest,
    judge: LLMJudge | None,
    settings: Settings,
    *,
    retry_transient: bool = False,
) -> list[EvaluationResult]:
    try:
        active_judge = judge or _build_default_judge(settings)
        return [evaluator(trace, active_judge) for evaluator in DEEP_EVALUATORS]
    except Exception as exc:
        if retry_transient and isinstance(exc, TRANSIENT_JUDGE_ERRORS):
            raise TransientEvaluationError(f"{type(exc).__name__}: {exc}") from exc
        return [
            EvaluationResult(
                evaluator_name=ERROR_EVALUATOR_NAME,
                evaluator_version=ERROR_EVALUATOR_VERSION,
                label="error",
                reason=f"Deep evaluation failed: {exc}",
                details={},
            )
        ]


def _build_default_judge(settings: Settings) -> LLMJudge:
    if not settings.openai_api_key:
        raise RuntimeError("No OpenAI API key configured for deep evaluation.")
    return OpenAIJudge()
