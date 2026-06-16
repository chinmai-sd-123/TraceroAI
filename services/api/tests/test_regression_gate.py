from app.eval.regression_gate import run_regression_gate

# Baseline measured 2026-06-16: 78% (7/9). Two misses are KNOWN deterministic
# limits kept as ground-truth gaps (both resolved by the deep LLM judge):
#   - healthy_refund_timeline: lexical overlap can't see that "5-7 business days"
#     answers "how long" (semantic equivalence) -> lands on needs_review.
#   - unsupported_claim_upload_encryption: whole-answer term-overlap averages, so
#     one fabricated claim in an otherwise grounded answer only dips groundedness
#     to needs_review, not fail. Per-claim (deep) groundedness is what catches it.
# This gate guards against regressions BELOW the baseline. Ratchet up as evaluators improve.
MIN_DIAGNOSIS_ACCURACY = 0.75


def test_quick_eval_diagnosis_accuracy_does_not_regress() -> None:
    report = run_regression_gate()

    failure_lines = "\n".join(
        f"  - {result.case_id}: expected '{result.expected}', got '{result.actual}'"
        for result in report.failures
    )
    assert report.accuracy >= MIN_DIAGNOSIS_ACCURACY, (
        f"Diagnosis accuracy {report.accuracy:.0%} fell below the "
        f"{MIN_DIAGNOSIS_ACCURACY:.0%} baseline.\nFailing cases:\n{failure_lines}"
    )
