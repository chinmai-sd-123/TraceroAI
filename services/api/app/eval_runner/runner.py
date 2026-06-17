"""The experiment harness core: run a dataset across variants, grade with an LLM
judge, aggregate per-variant metrics, and recommend a winner.

This produces an EvalRunIngestRequest (run_type="experiment") that the existing
POST /v1/eval-runs endpoint stores and the dashboard renders. Cost is bounded by
small datasets + a generation/grading cache so re-runs are free.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.eval_runner.datasets import Dataset
from app.eval_runner.rag import VariantConfig, run_rag
from app.schemas.eval_runs import (
    EvalMetricSummary,
    EvalRunIngestRequest,
    EvalRunSummary,
    ExperimentVariantResult,
)
from app.schemas.traces import TraceIngestRequest
from app.services.llm_judge import LLMJudge, OpenAIJudge
from app.services.quick_evaluation import run_quick_evaluation


@dataclass
class CaseOutcome:
    case_id: str
    question: str
    expected: str
    actual: str
    correct: bool
    reason: str
    diagnosis: str
    latency_ms: int
    grading_failed: bool = False


def _grade_with_retry(
    judge: LLMJudge,
    question: str,
    expected: str,
    actual: str,
    *,
    retries: int = 3,
    backoff_base: float = 2.0,
):
    """Grade correctness, retrying transient provider errors (429/503) with
    backoff. Returns (correct, reason, grading_failed). grading_failed=True means
    we could NOT get a verdict — distinct from a genuine incorrect answer.

    backoff_base=0 disables sleeping (used in tests)."""
    import time

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            verdict = judge.judge_answer_correctness(question, expected, actual)
            return verdict.correct, verdict.reason, False
        except Exception as exc:  # noqa: BLE001 - provider errors are opaque
            last_exc = exc
            if backoff_base and attempt < retries - 1:
                time.sleep(backoff_base * (attempt + 1))
    return False, f"grading_failed: {type(last_exc).__name__}", True


def _grade_case(
    case_id: str,
    question: str,
    expected: str,
    config: VariantConfig,
    judge: LLMJudge,
    backoff_base: float = 2.0,
) -> CaseOutcome:
    """Run RAG for one case, then grade correctness with the LLM judge."""
    rag = run_rag(question, config)

    # Run the quick evaluators too, so we capture the diagnosis for context.
    trace = TraceIngestRequest.model_validate(
        {
            "query": {"original": question},
            "retrieval": {"chunks": rag.chunks},
            "generation": {
                "model": config.as_dict()["model"],
                "answer": rag.answer,
            },
        }
    )
    trace = run_quick_evaluation(trace)

    correct, reason, grading_failed = _grade_with_retry(
        judge, question, expected, rag.answer, backoff_base=backoff_base
    )

    return CaseOutcome(
        case_id=case_id,
        question=question,
        expected=expected,
        actual=rag.answer,
        correct=correct,
        reason=reason,
        diagnosis=trace.diagnosis.label,
        latency_ms=rag.latency_ms,
        grading_failed=grading_failed,
    )


def _run_variant(
    dataset: Dataset, config: VariantConfig, judge: LLMJudge, backoff_base: float = 2.0
) -> tuple[ExperimentVariantResult, list[CaseOutcome]]:
    outcomes = [
        _grade_case(c.case_id, c.question, c.expected_answer, config, judge, backoff_base)
        for c in dataset.cases
    ]
    total = len(outcomes)
    gradeable = [o for o in outcomes if not o.grading_failed]
    ungradeable = total - len(gradeable)
    passed = sum(o.correct for o in gradeable)
    # Accuracy is over gradeable cases only, so a flaky grader can't fake a 0%.
    accuracy = passed / len(gradeable) if gradeable else 0.0
    avg_latency = round(sum(o.latency_ms for o in outcomes) / total) if total else 0

    variant = ExperimentVariantResult(
        variant_id=config.variant_id,
        name=config.name,
        config={**config.as_dict(), "ungradeable_cases": ungradeable},
        passed_cases=passed,
        failed_cases=len(gradeable) - passed,
        average_latency_ms=avg_latency,
        metrics=[
            EvalMetricSummary(metric_name="accuracy", score=round(accuracy, 3)),
        ],
    )
    return variant, outcomes


def _metric(variant: ExperimentVariantResult, name: str) -> float:
    for m in variant.metrics:
        if m.metric_name == name and m.score is not None:
            return m.score
    return 0.0


def recommend_winner(variants: list[ExperimentVariantResult]) -> ExperimentVariantResult:
    """Pick the best variant: highest accuracy, tie-break on lower latency."""
    return max(
        variants,
        key=lambda v: (_metric(v, "accuracy"), -(v.average_latency_ms or 0)),
    )


def run_experiment(
    dataset: Dataset,
    configs: list[VariantConfig],
    judge: LLMJudge | None = None,
    project_id: str = "experiments",
    backoff_base: float = 2.0,
) -> EvalRunIngestRequest:
    """Run the full experiment and build the EvalRun payload (with winner)."""
    if len(configs) < 2:
        raise ValueError("An experiment needs at least two variant configs to compare.")

    active_judge = judge or OpenAIJudge()
    variants: list[ExperimentVariantResult] = []
    for config in configs:
        variant, _ = _run_variant(dataset, config, active_judge, backoff_base)
        variants.append(variant)

    winner = recommend_winner(variants)
    total = len(dataset.cases)
    recommendation = (
        f"Variant '{winner.name}' ({winner.variant_id}) wins with "
        f"accuracy={_metric(winner, 'accuracy'):.2f} over {total} cases."
    )

    # The top-level summary describes the WINNING variant, so total/passed/pass_rate
    # are meaningful at a glance; per-variant detail lives in `variants`.
    win_total = winner.passed_cases + winner.failed_cases

    return EvalRunIngestRequest.model_validate(
        {
            "run_type": "experiment",
            "status": "completed",
            "project": {"project_id": project_id},
            "dataset": {
                "dataset_id": dataset.dataset_id,
                "name": dataset.name,
                "version": dataset.version,
            },
            "pipeline": {"pipeline_version": "experiment_harness_v1"},
            "summary": EvalRunSummary(
                total_cases=win_total,
                passed_cases=winner.passed_cases,
                failed_cases=winner.failed_cases,
                pass_rate=round(winner.passed_cases / win_total, 3) if win_total else 0.0,
                recommendation=recommendation,
            ),
            "variants": variants,
        }
    )
