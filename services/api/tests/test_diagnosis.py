from app.evaluators.diagnosis import diagnose_trace, is_refusal
from app.schemas.traces import EvaluationResult


def _eval(name: str, label: str) -> EvaluationResult:
    return EvaluationResult(evaluator_name=name, label=label)


def _all(context: str, grounded: str, answer: str) -> list[EvaluationResult]:
    return [
        _eval("context_relevance", context),
        _eval("groundedness", grounded),
        _eval("answer_relevance", answer),
    ]


def test_is_refusal_detects_decline_phrases() -> None:
    assert is_refusal("I don't know.")
    assert is_refusal("I'm sorry, I cannot answer that.")
    assert not is_refusal("Refunds take 5 to 7 business days.")
    assert not is_refusal("")


def test_refusal_diagnoses_as_correct_refusal_not_unsupported_claim() -> None:
    # Without the refusal flag, a failed-groundedness "I don't know" would be
    # mislabeled unsupported_claim; with it, it's a correct_refusal.
    evals = _all("needs_review", "fail", "fail")

    assert diagnose_trace(evals, refused=False).label == "unsupported_claim"
    assert diagnose_trace(evals, refused=True).label == "correct_refusal"


def test_refusal_when_context_relevant_is_wrong_answer_not_correct_refusal() -> None:
    # A refusal is only "correct" if the context genuinely lacked the answer. If
    # the context was relevant (the answer was there) but the model refused, that's
    # a WRONG refusal — an answerable question the model gave up on.
    relevant = _all("pass", "fail", "fail")  # context relevant, but refused
    assert diagnose_trace(relevant, refused=True).label == "wrong_answer"

    # Context genuinely irrelevant + refused -> still a correct refusal.
    irrelevant = _all("fail", "fail", "fail")
    assert diagnose_trace(irrelevant, refused=True).label == "correct_refusal"


def test_healthy_when_all_pass_and_not_refused() -> None:
    evals = _all("pass", "pass", "pass")
    assert diagnose_trace(evals).label == "healthy_answer"
