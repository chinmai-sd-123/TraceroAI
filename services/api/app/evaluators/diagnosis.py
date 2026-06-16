from app.schemas.traces import DiagnosisTrace, EvaluationResult

# Phrases that indicate the model declined to answer (e.g. context lacked the
# answer). A refusal is correct behavior, not an unsupported claim, so it must
# be diagnosed before the groundedness/relevance checks.
REFUSAL_MARKERS = (
    "i don't know",
    "i do not know",
    "i'm sorry",
    "i am sorry",
    "cannot answer",
    "can't answer",
    "not enough information",
    "no information",
    "based on the provided context",
)


def is_refusal(answer: str) -> bool:
    text = answer.strip().lower()
    if not text:
        return False
    return any(marker in text for marker in REFUSAL_MARKERS)


def diagnose_trace(
    evaluations: list[EvaluationResult], *, refused: bool = False
) -> DiagnosisTrace:
    by_name = {evaluation.evaluator_name: evaluation for evaluation in evaluations}

    context_relevance = by_name.get("context_relevance")
    groundedness = by_name.get("groundedness")
    answer_relevance = by_name.get("answer_relevance")

    # A correct refusal short-circuits: declining when the context doesn't
    # support an answer is desired behavior, not a failure.
    if refused:
        return DiagnosisTrace(
            label="correct_refusal",
            reason="The model declined to answer because the context did not support a confident answer.",
        )

    if context_relevance and context_relevance.label == "fail":
        return DiagnosisTrace(
            label="retrieval_miss",
            reason="Retrieved context does not sufficiently match the query.",
        )

    if groundedness and groundedness.label == "fail":
        return DiagnosisTrace(
            label="unsupported_claim",
            reason="The answer contains terms that are not supported by the retrieved context.",
        )

    if answer_relevance and answer_relevance.label == "fail":
        return DiagnosisTrace(
            label="wrong_answer",
            reason="The answer does not sufficiently address the query.",
        )

    if all(
        evaluation is not None and evaluation.label == "pass"
        for evaluation in [context_relevance, groundedness, answer_relevance]
    ):
        return DiagnosisTrace(
            label="healthy_answer",
            reason="Retrieval, grounding, and answer relevance checks all passed.",
        )

    return DiagnosisTrace(
        label="needs_review",
        reason="One or more evaluation checks require manual review.",
    )