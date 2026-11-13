"""The lexical diagnosis must not get worse than its measured baseline.

This gate runs the deterministic ingest-time tier only (no network), so it is the
same in CI and locally. The embedding and judge tiers are measured with
`python -m app.eval.benchmark`; see docs/evaluation-benchmark.md.

Baselines, measured 2026-11-13. Ratchet them up when the evaluators improve; a
drop below them fails CI with the cases that changed.
"""

from collections import Counter

from app.eval.constructed_cases import FACTS, build_cases
from app.eval.regression_gate import GOLDEN_PATH, load_golden_cases, run_regression_gate

# 7/9 on the hand-labelled cases. The two misses are lexical limits the judge
# handles: "5-7 business days" not recognised as answering "how long", and one
# invented claim diluted by an otherwise grounded answer.
MIN_HANDWRITTEN_ACCURACY = 0.75
# 68/117 on the full set. Lexical overlap never recognises a paraphrased correct
# answer (0/18 constructed healthy cases) and reads most refusals as correct.
MIN_FULL_SET_ACCURACY = 0.58


def _failure_lines(report) -> str:
    return "\n".join(
        f"  - {r.case_id}: expected '{r.expected}', got '{r.actual}'" for r in report.failures
    )


def test_handwritten_cases_do_not_regress() -> None:
    report = run_regression_gate(load_golden_cases(GOLDEN_PATH, constructed=False))
    assert report.accuracy >= MIN_HANDWRITTEN_ACCURACY, (
        f"Accuracy {report.accuracy:.0%} fell below {MIN_HANDWRITTEN_ACCURACY:.0%}.\n"
        + _failure_lines(report)
    )


def test_full_golden_set_does_not_regress() -> None:
    report = run_regression_gate()
    assert report.accuracy >= MIN_FULL_SET_ACCURACY, (
        f"Accuracy {report.accuracy:.1%} fell below {MIN_FULL_SET_ACCURACY:.0%}.\n"
        + _failure_lines(report)
    )


def test_constructed_cases_are_well_formed() -> None:
    cases = build_cases()
    assert len(cases) == 6 * len(FACTS)
    assert len({c["case_id"] for c in cases}) == len(cases)  # unique ids
    # Every construction yields its documented label.
    expected = {
        "healthy": "healthy_answer",
        "unsupported": "unsupported_claim",
        "retrieval_miss": "retrieval_miss",
        "correct_refusal": "correct_refusal",
        "wrong_refusal": "wrong_answer",
        "off_target": "wrong_answer",
    }
    assert {(c["construction"], c["expected_diagnosis"]) for c in cases} == set(expected.items())
    assert Counter(c["construction"] for c in cases) == {k: len(FACTS) for k in expected}
