"""Reproducible benchmarks for the evaluation engine — produces real, citable numbers.

Run:
    .venv/Scripts/python.exe -m app.eval.benchmark
    .venv/Scripts/python.exe -m app.eval.benchmark --latency-runs 30

Two benchmarks, both over the 9-case golden set (app/eval/golden_traces.json):

  (A) Diagnosis accuracy vs ground truth — for BOTH the deterministic quick eval
      and the LLM judge (deep eval), so they can be compared head to head. The
      judge benchmark is skipped (not faked) when no judge key is configured.

  (B) Eval-path latency — wall-clock p50/p95/mean of run_quick_evaluation over
      repeated runs, so the synchronous ingest-path cost is a measured number.

Numbers printed here are the only ones safe to cite: they are computed from
labeled cases at run time, not stored data (which may have been cleared).
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.eval.regression_gate import load_golden_cases
from app.evaluators.diagnosis import diagnose_from_deep, is_refusal
from app.schemas.traces import TraceIngestRequest
from app.services.deep_evaluation import DEEP_EVALUATORS, _build_default_judge
from app.services.quick_evaluation import run_quick_evaluation


@dataclass
class CaseOutcome:
    case_id: str
    expected: str
    actual: str

    @property
    def passed(self) -> bool:
        return self.actual == self.expected


def _accuracy(outcomes: list[CaseOutcome]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o.passed) / len(outcomes)


def _print_outcomes(title: str, outcomes: list[CaseOutcome]) -> None:
    passed = sum(1 for o in outcomes if o.passed)
    print(f"\n{title}: {_accuracy(outcomes):.0%} ({passed}/{len(outcomes)})")
    for o in outcomes:
        flag = "PASS" if o.passed else "FAIL"
        print(f"  {flag}  {o.case_id:<34} expected {o.expected:<18} got {o.actual}")


def benchmark_quick_accuracy(cases: list[dict]) -> list[CaseOutcome]:
    """Deterministic quick-eval diagnosis vs ground truth (no LLM)."""
    outcomes: list[CaseOutcome] = []
    for case in cases:
        trace = TraceIngestRequest(**case["trace"])
        evaluated = run_quick_evaluation(trace)
        outcomes.append(
            CaseOutcome(case["case_id"], case["expected_diagnosis"], evaluated.diagnosis.label)
        )
    return outcomes


class JudgeUnavailable(Exception):
    """The judge is not usable (no key, invalid key, wrong endpoint)."""


def benchmark_judge_accuracy(cases: list[dict]) -> list[CaseOutcome]:
    """LLM-judge (deep eval) diagnosis vs ground truth.

    Raises JudgeUnavailable when no judge is configured OR the configured judge
    rejects the call (bad key / wrong endpoint) — we never fabricate a judge
    number, and an unusable judge is reported as such, not as a crash.

    Runs the deep evaluators directly on the in-memory trace (no DB round-trip),
    then re-diagnoses with the same diagnose_from_deep used in production.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise JudgeUnavailable("no judge key configured (TRACEROAI_OPENAI_API_KEY)")

    try:
        judge = _build_default_judge(settings)
        outcomes: list[CaseOutcome] = []
        for case in cases:
            trace = TraceIngestRequest(**case["trace"])
            results = [evaluator(trace, judge) for evaluator in DEEP_EVALUATORS]
            refused = not trace.generation.answered or is_refusal(trace.generation.answer)
            diagnosis = diagnose_from_deep(results, refused=refused)
            actual = diagnosis.label if diagnosis is not None else "needs_review"
            outcomes.append(CaseOutcome(case["case_id"], case["expected_diagnosis"], actual))
        return outcomes
    except Exception as exc:  # bad key, wrong endpoint, provider error
        raise JudgeUnavailable(str(exc)) from exc


def benchmark_latency(cases: list[dict], runs: int) -> dict[str, float]:
    """Wall-clock latency of the synchronous quick-eval path, in milliseconds.

    Times one run_quick_evaluation per (case x run) and reports the distribution.
    This is the real per-trace cost the ingest path pays before returning 202.
    """
    traces = [TraceIngestRequest(**case["trace"]) for case in cases]
    samples_ms: list[float] = []
    for _ in range(runs):
        for trace in traces:
            # Re-parse so we time a fresh trace each iteration (no warm caches on the object).
            fresh = trace.model_copy(deep=True)
            start = time.perf_counter()
            run_quick_evaluation(fresh)
            samples_ms.append((time.perf_counter() - start) * 1000)

    samples_ms.sort()
    n = len(samples_ms)

    def pct(p: float) -> float:
        idx = min(max(int(round((p / 100) * n)) - 1, 0), n - 1)
        return samples_ms[idx]

    return {
        "samples": n,
        "mean_ms": sum(samples_ms) / n,
        "p50_ms": pct(50),
        "p95_ms": pct(95),
        "max_ms": samples_ms[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="TraceroAI evaluation-engine benchmarks")
    parser.add_argument(
        "--latency-runs",
        type=int,
        default=20,
        help="How many times to replay the golden set when timing the eval path.",
    )
    args = parser.parse_args()

    cases = load_golden_cases()
    settings = get_settings()

    print("=" * 70)
    print(f"TraceroAI evaluation benchmark — {len(cases)} golden cases")
    print(f"embedding_model={settings.embedding_model!r}  judge_model={settings.judge_model!r}")
    print("=" * 70)

    # (A) Accuracy — quick vs judge, head to head.
    quick = benchmark_quick_accuracy(cases)
    _print_outcomes("Quick eval (deterministic) accuracy vs ground truth", quick)

    try:
        judge = benchmark_judge_accuracy(cases)
        _print_outcomes("LLM-judge (deep eval) accuracy vs ground truth", judge)
    except JudgeUnavailable as exc:
        print(
            f"\nLLM-judge accuracy: SKIPPED — judge unavailable ({exc}). "
            "Not reporting a fabricated number."
        )

    # (B) Latency of the synchronous eval path.
    lat = benchmark_latency(cases, args.latency_runs)
    print(
        f"\nQuick-eval path latency ({int(lat['samples'])} samples, "
        f"{args.latency_runs} runs x {len(cases)} cases):"
    )
    print(f"  mean {lat['mean_ms']:.1f} ms   p50 {lat['p50_ms']:.1f} ms   "
          f"p95 {lat['p95_ms']:.1f} ms   max {lat['max_ms']:.1f} ms")
    print(
        "  NOTE: includes the embedding API round-trip when a key is set; "
        "with no key it measures the lexical fallback only."
    )
    print()


if __name__ == "__main__":
    main()
