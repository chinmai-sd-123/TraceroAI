from app.schemas.traces import DiagnosisTrace, EvaluationResult


def diagnose_trace(evaluations: list[EvaluationResult]) -> DiagnosisTrace:
    by_name = {evaluation.evaluator_name: evaluation for evaluation in evaluations}

    context_relevance = by_name.get("context_relevance")
    groundedness = by_name.get("groundedness")
    answer_relevance = by_name.get("answer_relevance")

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