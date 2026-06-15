from app.schemas.traces import EvaluationResult, TraceIngestRequest
from app.services.llm_judge import LLMJudge


EVALUATOR_NAME = "claim_groundedness"
EVALUATOR_VERSION = "llm_judge_openai_v1"


def evaluate_deep_groundedness(
    trace: TraceIngestRequest, judge: LLMJudge
) -> EvaluationResult:
    context = "\n\n".join(chunk.text for chunk in trace.retrieval.chunks)
    answer = trace.generation.answer

    verdict = judge.judge_claim_groundedness(answer=answer, context=context)
    claims = verdict.claims

    if not claims:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION,
            label="needs_review",
            score=None,
            reason="The judge extracted no factual claims from the answer.",
            details={"claims": []},
        )

    supported = [claim for claim in claims if claim.supported]
    score = round(len(supported) / len(claims), 3)

    if len(supported) == len(claims):
        label = "grounded"
        reason = f"All {len(claims)} claims are supported by the retrieved context."
    else:
        unsupported = len(claims) - len(supported)
        label = "not_grounded"
        reason = f"{unsupported} of {len(claims)} claims are not supported by the context."

    return EvaluationResult(
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        label=label,
        score=score,
        reason=reason,
        details={"claims": [claim.model_dump() for claim in claims]},
    )
