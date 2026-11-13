from uuid import UUID

import openai

from app.core.config import Settings, get_settings
from app.core.metrics import DEEP_EVALUATIONS
from app.db.session import SessionLocal
from app.evaluators.deep_groundedness import evaluate_deep_groundedness
from app.evaluators.deep_relevance import (
    evaluate_deep_answer_relevance,
    evaluate_deep_context_relevance,
)
from app.evaluators.diagnosis import diagnose_from_deep, is_refusal
from app.schemas.traces import DeepEvaluationStatus, DiagnosisTrace, EvaluationResult, Trace
from app.services.embeddings import EmbeddingClient
from app.services.llm_judge import LLMJudge, OpenAIJudge
from app.services.quick_evaluation import run_quick_evaluation
from app.services.trace_repository import TraceRepository


DEEP_EVALUATORS = (
    evaluate_deep_context_relevance,
    evaluate_deep_groundedness,
    evaluate_deep_answer_relevance,
)
# Per judge call when a request is waiting (sync_deep_eval). Three calls, no
# provider retries: the request waits at most about 45 seconds for the judge.
INLINE_JUDGE_TIMEOUT_SECONDS = 15.0
ERROR_EVALUATOR_NAME = "deep_evaluation"
DEEP_EVALUATOR_NAMES = {
    evaluate_deep_context_relevance: "deep_context_relevance",
    evaluate_deep_groundedness: "claim_groundedness",
    evaluate_deep_answer_relevance: "deep_answer_relevance",
}
# Extra attempts for a judge call that fails for a reason other than the
# provider (usually a verdict that doesn't match the expected structure).
VERDICT_RETRIES = 1
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
    inline: bool = False,
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

    inline=True (a request waiting on the result, i.e. sync_deep_eval) gives
    each judge call a shorter timeout and no provider retries, so the caller
    waits at most a bounded time.

    No database connection is held while the providers are called: the trace is
    read in one short session and the results written in another, as a single
    UPDATE that leaves other parts of the trace (feedback) alone.
    """
    settings = get_settings()
    semantic = embedder is not None or bool(settings.openai_api_key)
    judge_available = settings.deep_eval_enabled and (
        judge is not None or bool(settings.openai_api_key)
    )

    with SessionLocal() as db:
        record = TraceRepository(db).get(trace_id)
        if record is None:
            return
        trace = Trace(**record.payload)

    quick: list[EvaluationResult] | None = None
    diagnosis: DiagnosisTrace | None = None
    if semantic:
        refreshed = run_quick_evaluation(
            trace.model_copy(deep=True), semantic=True, embedder=embedder
        )
        quick = refreshed.evaluations.quick
        diagnosis = refreshed.diagnosis

    deep: list[EvaluationResult] | None = None
    # No judge configured is a setup choice, not a failure: record "skipped"
    # rather than an error result on every trace.
    deep_status: DeepEvaluationStatus = "skipped"
    if judge_available:
        deep = _evaluate(trace, judge, settings, retry_transient=retry_transient, inline=inline)
        deep_status = _deep_status(deep)
        # Re-diagnose from the judge's verdict — it's more reliable than the
        # quick eval. If the judge errored or yielded nothing usable,
        # diagnose_from_deep returns None and the quick diagnosis stands.
        refused = not trace.generation.answered or is_refusal(trace.generation.answer)
        deep_diagnosis = diagnose_from_deep(deep, refused=refused)
        if deep_diagnosis is not None:
            diagnosis = deep_diagnosis

    with SessionLocal() as db:
        TraceRepository(db).set_evaluations(
            trace_id, quick=quick, deep=deep, diagnosis=diagnosis, deep_status=deep_status
        )
    DEEP_EVALUATIONS.labels(deep_status).inc()


def judge_configured() -> bool:
    """Whether background evaluation can do anything: it needs the provider key
    for embeddings and for the judge."""
    return bool(get_settings().openai_api_key)


def initial_deep_status() -> DeepEvaluationStatus:
    """The judge status a newly ingested trace starts with."""
    settings = get_settings()
    return "pending" if settings.deep_eval_enabled and settings.openai_api_key else "skipped"


def _deep_status(deep: list[EvaluationResult]) -> DeepEvaluationStatus:
    errors = sum(1 for result in deep if result.label == "error")
    if errors == 0:
        return "complete"
    return "failed" if errors == len(deep) else "partial"


def _evaluate(
    trace: Trace,
    judge: LLMJudge | None,
    settings: Settings,
    *,
    retry_transient: bool = False,
    inline: bool = False,
) -> list[EvaluationResult]:
    try:
        active_judge = judge or _build_default_judge(settings, inline=inline)
    except Exception as exc:
        return [_error_result(ERROR_EVALUATOR_NAME, exc)]
    # Each judge call stands on its own: one failing doesn't discard the others.
    return [
        _run_evaluator(evaluator, trace, active_judge, retry_transient=retry_transient)
        for evaluator in DEEP_EVALUATORS
    ]


def _run_evaluator(evaluator, trace: Trace, judge: LLMJudge, *, retry_transient: bool):
    last_error: Exception | None = None
    for _ in range(1 + VERDICT_RETRIES):
        try:
            return evaluator(trace, judge)
        except TRANSIENT_JUDGE_ERRORS as exc:
            # The provider client has already retried these.
            if retry_transient:
                raise TransientEvaluationError(f"{type(exc).__name__}: {exc}") from exc
            last_error = exc
            break
        except Exception as exc:  # e.g. a verdict that didn't parse: ask again once
            last_error = exc
    return _error_result(DEEP_EVALUATOR_NAMES[evaluator], last_error)


def _error_result(name: str, error: Exception | None) -> EvaluationResult:
    return EvaluationResult(
        evaluator_name=name,
        evaluator_version=ERROR_EVALUATOR_VERSION,
        label="error",
        reason=f"Judge call failed: {type(error).__name__}: {error}",
        details={},
    )


def _build_default_judge(settings: Settings, *, inline: bool = False) -> LLMJudge:
    if not settings.openai_api_key:
        raise RuntimeError("No OpenAI API key configured for deep evaluation.")
    if inline:
        return OpenAIJudge(timeout=INLINE_JUDGE_TIMEOUT_SECONDS, max_retries=0)
    return OpenAIJudge()
