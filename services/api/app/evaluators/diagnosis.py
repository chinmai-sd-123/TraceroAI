import re

from app.schemas.traces import DiagnosisTrace, EvaluationResult

# Patterns for an explicit decline (e.g. the context lacked the answer). A refusal
# is correct behavior, not an unsupported claim, so it must be diagnosed before the
# groundedness/relevance checks.
#
# Each pattern is a decline *statement*, not a hedge: "Based on the provided
# context, ..." and "I'm sorry, ..." usually open a real answer, so on their own
# they are deliberately not refusals.
REFUSAL_PATTERNS = (
    r"\bi (?:do not|don't) know\b",
    r"\bi (?:cannot|can't|am unable to|'m unable to|am not able to|'m not able to) "
    r"(?:answer|find|determine|say|tell|provide|help)\b",
    r"\b(?:cannot|can't|could not|couldn't) be (?:answered|determined)\b",
    r"\b(?:i|we) (?:could not|couldn't|did not|didn't) find\b",
    r"\bnot enough (?:information|context|detail)",
    r"\b(?:there is|there's) no (?:relevant )?information\b",
    r"\bi (?:do not|don't) have (?:enough |any |the )?(?:relevant )?information\b",
    r"\b(?:context|documents?|sources?) (?:does not|doesn't|do not|don't) "
    r"(?:contain|include|mention|provide|specify|say|cover)\b",
)
_REFUSAL_RE = re.compile("|".join(REFUSAL_PATTERNS))
_FIRST_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def is_refusal(answer: str) -> bool:
    """True if the answer declines to answer.

    Only the first sentence is checked: a model that declines leads with it,
    while "Refunds take 5-7 days. The context doesn't mention fees." is a real
    (partial) answer that should be evaluated like any other.
    """
    # LLMs often emit curly apostrophes (don’t); normalize so patterns match.
    text = answer.strip().lower().replace("’", "'")
    if not text:
        return False
    first_sentence = _FIRST_SENTENCE_RE.split(text, maxsplit=1)[0]
    return _REFUSAL_RE.search(first_sentence) is not None


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