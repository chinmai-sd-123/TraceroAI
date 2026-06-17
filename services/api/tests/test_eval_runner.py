"""Tests for the RAG experiment harness.

Uses a stub judge (no network) so grading is deterministic. The harness depends
on the LLMJudge contract, so the stub substitutes cleanly for OpenAIJudge.
"""

from app.eval_runner.datasets import Dataset, DatasetCase
from app.eval_runner.rag import VariantConfig
from app.eval_runner.runner import recommend_winner, run_experiment
from app.schemas.eval_runs import EvalMetricSummary, ExperimentVariantResult
from app.services.llm_judge import CorrectnessVerdict


class StubJudge:
    """Marks an answer correct if the first 3 expected words appear in it."""

    def judge_answer_correctness(self, question, expected, actual) -> CorrectnessVerdict:
        key = " ".join(expected.lower().split()[:3])
        ok = key in actual.lower()
        return CorrectnessVerdict(correct=ok, reason="stub")


class AlwaysFailsJudge:
    def judge_answer_correctness(self, question, expected, actual) -> CorrectnessVerdict:
        raise RuntimeError("provider down")


def tiny_dataset() -> Dataset:
    return Dataset(
        dataset_id="tiny",
        name="Tiny",
        version="v1",
        cases=[
            DatasetCase("refund", "How long does a refund take?",
                        "Refunds are processed within 5 to 7 business days after the request is approved."),
            DatasetCase("upload", "What is the maximum file upload size?",
                        "The maximum file upload size is 100 megabytes per file."),
        ],
    )


def two_variants() -> list[VariantConfig]:
    return [
        VariantConfig("a", "Variant A", top_k=3, prompt_variant="v2"),
        VariantConfig("b", "Variant B", top_k=5, prompt_variant="v2"),
    ]


def test_run_experiment_produces_valid_experiment_payload() -> None:
    run = run_experiment(tiny_dataset(), two_variants(), judge=StubJudge())

    assert run.run_type == "experiment"
    assert len(run.variants) == 2
    assert run.summary.recommendation is not None
    # Each variant reports an accuracy metric.
    for v in run.variants:
        assert any(m.metric_name == "accuracy" for m in v.metrics)


def test_recommend_winner_prefers_higher_accuracy() -> None:
    low = ExperimentVariantResult(
        variant_id="low", name="Low", passed_cases=1, failed_cases=3,
        metrics=[EvalMetricSummary(metric_name="accuracy", score=0.25)],
    )
    high = ExperimentVariantResult(
        variant_id="high", name="High", passed_cases=3, failed_cases=1,
        metrics=[EvalMetricSummary(metric_name="accuracy", score=0.75)],
    )
    assert recommend_winner([low, high]).variant_id == "high"


def test_recommend_winner_tiebreaks_on_latency() -> None:
    slow = ExperimentVariantResult(
        variant_id="slow", name="Slow", passed_cases=2, failed_cases=0,
        average_latency_ms=900,
        metrics=[EvalMetricSummary(metric_name="accuracy", score=1.0)],
    )
    fast = ExperimentVariantResult(
        variant_id="fast", name="Fast", passed_cases=2, failed_cases=0,
        average_latency_ms=200,
        metrics=[EvalMetricSummary(metric_name="accuracy", score=1.0)],
    )
    assert recommend_winner([slow, fast]).variant_id == "fast"


def test_grading_failure_does_not_count_as_wrong() -> None:
    run = run_experiment(tiny_dataset(), two_variants(), judge=AlwaysFailsJudge(), backoff_base=0)
    # Every grade failed -> 0 gradeable cases, accuracy 0, all flagged ungradeable.
    for v in run.variants:
        assert v.passed_cases == 0
        assert v.failed_cases == 0  # not counted as wrong
        assert v.config["ungradeable_cases"] == 2


def test_experiment_requires_two_variants() -> None:
    import pytest

    with pytest.raises(ValueError):
        run_experiment(tiny_dataset(), [VariantConfig("a", "A")], judge=StubJudge())
