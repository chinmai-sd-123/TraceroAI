from app.eval.regression_gate import run_regression_gate

# Baseline measured 2026-06-16: 75% (3/4). The one miss (healthy_refund_timeline)
# is a known context_relevance limitation: lexical term-overlap can't see that
# "5-7 business days" answers "how long...". Tracked as a backlog item
# (incl. an asymmetric-stemming bug in normalize_token).
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
