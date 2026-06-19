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


# Maps deep (LLM-judge) evaluator names+labels onto the deterministic
# name/label vocabulary that diagnose_trace reasons over, so a single
# diagnosis function serves both the quick and deep layers.
_DEEP_NAME_MAP = {
    "deep_context_relevance": "context_relevance",
    "claim_groundedness": "groundedness",
    "deep_answer_relevance": "answer_relevance",
}
_DEEP_PASS_LABELS = {"relevant", "grounded"}
_DEEP_FAIL_LABELS = {"irrelevant", "not_grounded"}


def diagnose_from_deep(
    deep_evaluations: list[EvaluationResult], *, refused: bool = False
) -> DiagnosisTrace | None:
    """Diagnose a trace from deep LLM-judge results.

    Returns None if the deep results aren't usable (e.g. the judge errored or
    produced no recognizable verdict), so callers can fall back to the
    deterministic diagnosis instead of masking a failure.
    """
    mapped: list[EvaluationResult] = []
    for evaluation in deep_evaluations:
        name = _DEEP_NAME_MAP.get(evaluation.evaluator_name)
        if name is None:
            continue
        if evaluation.label in _DEEP_PASS_LABELS:
            label = "pass"
        elif evaluation.label in _DEEP_FAIL_LABELS:
            label = "fail"
        else:
            label = "needs_review"
        mapped.append(evaluation.model_copy(update={"evaluator_name": name, "label": label}))

    if not mapped:
        return None
    return diagnose_trace(mapped, refused=refused)


def diagnose_trace(
    evaluations: list[EvaluationResult], *, refused: bool = False
) -> DiagnosisTrace:
    by_name = {evaluation.evaluator_name: evaluation for evaluation in evaluations}

    context_relevance = by_name.get("context_relevance")
    groundedness = by_name.get("groundedness")
    answer_relevance = by_name.get("answer_relevance")

    # A refusal is only CORRECT when the context genuinely lacked the answer.
    # If the model refused but the retrieved context was relevant (the answer was
    # there), that's a WRONG refusal — the model gave up on an answerable question.
    if refused:
        if context_relevance and context_relevance.label == "pass":
            return DiagnosisTrace(
                label="wrong_answer",
                reason="The model refused, but the retrieved context was relevant — the question was answerable.",
            )
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