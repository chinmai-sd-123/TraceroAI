from uuid import UUID

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.evaluators.deep_groundedness import evaluate_deep_groundedness
from app.evaluators.deep_relevance import (
    evaluate_deep_answer_relevance,
    evaluate_deep_context_relevance,
)
from app.schemas.traces import EvaluationResult, TraceIngestRequest
from app.services.llm_judge import LLMJudge, OpenAIJudge
from app.services.trace_repository import TraceRepository


DEEP_EVALUATORS = (
    evaluate_deep_context_relevance,
    evaluate_deep_groundedness,
    evaluate_deep_answer_relevance,
)
ERROR_EVALUATOR_NAME = "deep_evaluation"
ERROR_EVALUATOR_VERSION = "llm_judge_openai_v1"


def run_deep_evaluation(trace_id: UUID, judge: LLMJudge | None = None) -> None:
    settings = get_settings()
    if not settings.deep_eval_enabled:
        return

    db = SessionLocal()
    try:
        repository = TraceRepository(db)
        record = repository.get(trace_id)
        if record is None:
            return

        trace = TraceIngestRequest(**record.payload)
        results = _evaluate(trace, judge, settings)
        repository.set_deep_evaluations(trace_id, results)
    finally:
        db.close()


def _evaluate(
    trace: TraceIngestRequest, judge: LLMJudge | None, settings: Settings
) -> list[EvaluationResult]:
    try:
        active_judge = judge or _build_default_judge(settings)
        return [evaluator(trace, active_judge) for evaluator in DEEP_EVALUATORS]
    except Exception as exc:
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
