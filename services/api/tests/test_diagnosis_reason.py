"""A judge-decided diagnosis explains itself in the judge's words.

Found in field trial 1: the dashboard showed "The answer contains terms that are
not supported by the retrieved context" (wording for the term-overlap estimate)
while the judge's own result named the claim that was wrong.
"""

from app.evaluators.diagnosis import diagnose_from_deep, diagnose_trace
from app.schemas.traces import EvaluationResult


def _judge(groundedness_label: str = "grounded", context_label: str = "relevant") -> list[EvaluationResult]:
    return [
        EvaluationResult(
            evaluator_name="deep_context_relevance",
            label=context_label,
            reason="The context covers middleware ordering." if context_label == "relevant" else "The context is about CORS, not middleware.",
        ),
        EvaluationResult(
            evaluator_name="claim_groundedness",
            label=groundedness_label,
            reason="2 of 8 claims are not supported by the context.",
            details={
                "claims": [
                    {"claim": "Middlewares wrap the app.", "supported": True, "reason": "Stated."},
                    {
                        "claim": "On the request path, middlewares run from innermost to outermost.",
                        "supported": False,
                        "reason": "The context says the outermost middleware runs first.",
                    },
                ]
            },
        ),
        EvaluationResult(evaluator_name="deep_answer_relevance", label="relevant", reason="Answers the question."),
    ]


def test_grounding_failure_names_the_unsupported_claim() -> None:
    diagnosis = diagnose_from_deep(_judge(groundedness_label="not_grounded"))
    assert diagnosis is not None
    assert diagnosis.label == "unsupported_claim" and diagnosis.source == "judge"
    assert diagnosis.reason.startswith("2 of 8 claims are not supported by the context.")
    assert '"On the request path, middlewares run from innermost to outermost."' in diagnosis.reason
    assert "outermost middleware runs first" in diagnosis.reason
    assert "terms" not in diagnosis.reason


def test_retrieval_miss_uses_the_judges_reason() -> None:
    diagnosis = diagnose_from_deep(_judge(context_label="irrelevant"))
    assert diagnosis is not None
    assert diagnosis.label == "retrieval_miss"
    assert diagnosis.reason == "The context is about CORS, not middleware."


def test_estimates_keep_the_fixed_wording() -> None:
    estimate = [
        EvaluationResult(evaluator_name="context_relevance", label="pass", reason="overlap 0.4"),
        EvaluationResult(evaluator_name="groundedness", label="fail", reason="overlap 0.1"),
        EvaluationResult(evaluator_name="answer_relevance", label="pass", reason="overlap 0.5"),
    ]
    diagnosis = diagnose_trace(estimate, source="lexical")
    assert diagnosis.label == "unsupported_claim"
    assert diagnosis.reason == "The answer makes claims the retrieved context doesn't support."


def test_a_judge_refusal_keeps_its_explanation() -> None:
    diagnosis = diagnose_from_deep(_judge(), refused=True)
    assert diagnosis is not None
    assert diagnosis.label == "wrong_answer"
    assert diagnosis.reason.startswith("The model refused")
