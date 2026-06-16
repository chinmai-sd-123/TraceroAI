from app.schemas.traces import EvaluationResult, TraceIngestRequest
from app.services.llm_judge import LLMJudge, RelevanceVerdict


CONTEXT_EVALUATOR_NAME = "deep_context_relevance"
ANSWER_EVALUATOR_NAME = "deep_answer_relevance"
EVALUATOR_VERSION = "llm_judge_openai_v1"


def evaluate_deep_context_relevance(
    trace: TraceIngestRequest, judge: LLMJudge
) -> EvaluationResult:
    query = trace.query.rewritten or trace.query.original
    context = "\n\n".join(chunk.text for chunk in trace.retrieval.chunks)

    verdict = judge.judge_context_relevance(query=query, context=context)
    return _to_result(CONTEXT_EVALUATOR_NAME, verdict)


def evaluate_deep_answer_relevance(
    trace: TraceIngestRequest, judge: LLMJudge
) -> EvaluationResult:
    query = trace.query.rewritten or trace.query.original

    verdict = judge.judge_answer_relevance(query=query, answer=trace.generation.answer)
    return _to_result(ANSWER_EVALUATOR_NAME, verdict)


def _to_result(name: str, verdict: RelevanceVerdict) -> EvaluationResult:
    return EvaluationResult(
        evaluator_name=name,
        evaluator_version=EVALUATOR_VERSION,
        label="relevant" if verdict.relevant else "irrelevant",
        score=1.0 if verdict.relevant else 0.0,
        reason=verdict.reason,
        details={},
    )
