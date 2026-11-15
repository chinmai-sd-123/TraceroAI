"""The scheduled benchmark's pass/fail bars."""

from app.eval.benchmark import threshold_failures


def _report(accuracy_per_run, agreement=0.97):
    return {"tiers": {"judge": {"accuracy": accuracy_per_run[0], "accuracy_per_run": accuracy_per_run,
                                "self_agreement": agreement}}}


def test_no_bars_never_fails() -> None:
    assert threshold_failures({"tiers": {}}, None, None) == []


def test_meeting_the_bars_passes() -> None:
    assert threshold_failures(_report([0.94, 0.95, 0.96]), 0.9, 0.9) == []


def test_the_worst_run_is_what_counts() -> None:
    failures = threshold_failures(_report([0.95, 0.88, 0.96]), 0.9, None)
    assert failures == ["judge accuracy 88.0% is below 90.0%"]


def test_low_self_agreement_fails() -> None:
    failures = threshold_failures(_report([0.95], agreement=0.8), None, 0.9)
    assert failures == ["judge self-agreement 80.0% is below 90.0%"]


def test_a_skipped_judge_fails_a_bar_that_was_asked_for() -> None:
    report = {"tiers": {"judge": {"skipped": "no provider key"}}}
    assert threshold_failures(report, 0.9, None) == ["the judge tier didn't run (no provider key)"]
