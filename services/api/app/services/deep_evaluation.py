from uuid import UUID

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.evaluators.deep_groundedness import (
    EVALUATOR_NAME,
    EVALUATOR_VERSION,
    evaluate_deep_groundedness,
)
from app.schemas.traces import EvaluationResult, TraceIngestRequest
from app.services.llm_judge import LLMJudge, OpenAIJudge
from app.services.trace_repository import TraceRepository


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
        result = _evaluate(trace, judge, settings)
        repository.set_deep_evaluations(trace_id, [result])
    finally:
        db.close()


def _evaluate(
    trace: TraceIngestRequest, judge: LLMJudge | None, settings: Settings
) -> EvaluationResult:
    try:
        active_judge = judge or _build_default_judge(settings)
        return evaluate_deep_groundedness(trace, active_judge)
    except Exception as exc:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION,
            label="error",
            reason=f"Deep evaluation failed: {exc}",
            details={},
        )


def _build_default_judge(settings: Settings) -> LLMJudge:
    if not settings.openai_api_key:
        raise RuntimeError("No OpenAI API key configured for deep evaluation.")
    return OpenAIJudge()
