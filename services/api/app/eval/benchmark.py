"""Diagnosis accuracy of each evaluation tier, measured on the golden set.

Run from services/api (a judge needs TRACEROAI_OPENAI_API_KEY; it makes real
provider calls: about 3 per case per --repeat for the judge, 1 per case for
embeddings):

    python -m app.eval.benchmark                    # lexical, embedding, judge
    python -m app.eval.benchmark --repeat 3         # judge self-agreement too
    python -m app.eval.benchmark --report out.json  # save every verdict

The golden set is the hand-labelled cases (golden_traces.json) plus the
constructed ones (constructed_cases.py). For each tier this prints accuracy and
per-label precision and recall. A tier that can't run (no key, provider error)
is reported as skipped; no number is ever estimated.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.eval.regression_gate import load_golden_cases
from app.evaluators.diagnosis import diagnose_from_deep, is_refusal
from app.schemas.traces import Trace
from app.services.deep_evaluation import DEEP_EVALUATORS, _build_default_judge
from app.services.quick_evaluation import run_quick_evaluation

LABELS = ("healthy_answer", "correct_refusal", "retrieval_miss", "unsupported_claim", "wrong_answer")


@dataclass
class Verdict:
    case_id: str
    construction: str
    expected: str
    actual: str

    @property
    def passed(self) -> bool:
        return self.actual == self.expected


class TierUnavailable(Exception):
    """The tier can't run here (no key, rejected key, provider down)."""


# --- tiers ---


def lexical_tier(cases: list[dict]) -> list[Verdict]:
    return [
        _verdict(case, run_quick_evaluation(Trace(**case["trace"]), semantic=False).diagnosis.label)
        for case in cases
    ]


def embedding_tier(cases: list[dict], workers: int) -> list[Verdict]:
    if not get_settings().openai_api_key:
        raise TierUnavailable("no provider key (TRACEROAI_OPENAI_API_KEY)")

    def one(case: dict) -> Verdict:
        evaluated = run_quick_evaluation(Trace(**case["trace"]), semantic=True)
        if evaluated.diagnosis.source != "embedding":
            # The evaluators fall back to term overlap when the embeddings call
            # fails; counting those would report lexical accuracy as semantic.
            raise TierUnavailable("the embeddings call failed")
        return _verdict(case, evaluated.diagnosis.label)

    return _parallel(one, cases, workers)


def judge_tier(cases: list[dict], workers: int) -> list[Verdict]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise TierUnavailable("no provider key (TRACEROAI_OPENAI_API_KEY)")
    judge = _build_default_judge(settings)

    def one(case: dict) -> Verdict:
        trace = Trace(**case["trace"])
        results = [evaluator(trace, judge) for evaluator in DEEP_EVALUATORS]
        refused = not trace.generation.answered or is_refusal(trace.generation.answer)
        diagnosis = diagnose_from_deep(results, refused=refused)
        return _verdict(case, diagnosis.label if diagnosis is not None else "needs_review")

    return _parallel(one, cases, workers)


def _verdict(case: dict, actual: str) -> Verdict:
    return Verdict(
        case["case_id"], case.get("construction", "handwritten"), case["expected_diagnosis"], actual
    )


def _parallel(fn, cases: list[dict], workers: int) -> list[Verdict]:
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, cases))
    except TierUnavailable:
        raise
    except Exception as exc:  # bad key, wrong endpoint, provider error
        raise TierUnavailable(f"{type(exc).__name__}: {exc}") from exc


# --- scoring ---


def accuracy(verdicts: list[Verdict]) -> float:
    return sum(v.passed for v in verdicts) / len(verdicts) if verdicts else 0.0


def per_label(verdicts: list[Verdict]) -> dict[str, dict[str, float | int | None]]:
    """Precision and recall for each diagnosis label."""
    scores: dict[str, dict[str, float | int | None]] = {}
    for label in LABELS:
        tp = sum(1 for v in verdicts if v.expected == label and v.actual == label)
        predicted = sum(1 for v in verdicts if v.actual == label)
        actual = sum(1 for v in verdicts if v.expected == label)
        scores[label] = {
            "support": actual,
            "precision": round(tp / predicted, 3) if predicted else None,
            "recall": round(tp / actual, 3) if actual else None,
        }
    return scores


def by_construction(verdicts: list[Verdict]) -> dict[str, str]:
    total, passed = Counter(), Counter()
    for v in verdicts:
        total[v.construction] += 1
        passed[v.construction] += v.passed
    return {k: f"{passed[k]}/{total[k]}" for k in total}


def agreement(runs: list[list[Verdict]]) -> float:
    """Share of cases where every judge run gave the same label."""
    if len(runs) < 2:
        return 1.0
    same = sum(1 for labels in zip(*runs) if len({v.actual for v in labels}) == 1)
    return same / len(runs[0])


# --- output ---


def _print_tier(name: str, verdicts: list[Verdict]) -> None:
    print(f"\n{name}: {accuracy(verdicts):.1%} ({sum(v.passed for v in verdicts)}/{len(verdicts)})")
    print(f"  {'label':<18} {'support':>7} {'precision':>9} {'recall':>7}")
    for label, s in per_label(verdicts).items():
        fmt = lambda x: "  -  " if x is None else f"{x:.2f}"  # noqa: E731
        print(f"  {label:<18} {s['support']:>7} {fmt(s['precision']):>9} {fmt(s['recall']):>7}")
    print("  by construction: " + ", ".join(f"{k} {v}" for k, v in by_construction(verdicts).items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnosis accuracy per evaluation tier")
    parser.add_argument("--repeat", type=int, default=1, help="judge runs, for self-agreement")
    parser.add_argument("--workers", type=int, default=8, help="parallel provider calls")
    parser.add_argument("--report", type=Path, help="write every verdict to this JSON file")
    parser.add_argument("--no-provider", action="store_true", help="lexical tier only")
    args = parser.parse_args()

    cases = load_golden_cases()
    settings = get_settings()
    print(f"TraceroAI diagnosis benchmark: {len(cases)} cases "
          f"({dict(Counter(c['expected_diagnosis'] for c in cases))})")
    print(f"judge_model={settings.judge_model!r} embedding_model={settings.embedding_model!r}")

    report: dict = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cases": len(cases),
        "judge_model": settings.judge_model,
        "embedding_model": settings.embedding_model,
        "tiers": {},
    }

    def record(name: str, verdicts: list[Verdict], extra: dict | None = None) -> None:
        _print_tier(name, verdicts)
        report["tiers"][name] = {
            "accuracy": round(accuracy(verdicts), 4),
            "per_label": per_label(verdicts),
            "by_construction": by_construction(verdicts),
            "verdicts": [asdict(v) for v in verdicts],
            **(extra or {}),
        }

    record("lexical", lexical_tier(cases))

    if not args.no_provider:
        started = time.perf_counter()
        try:
            record("embedding", embedding_tier(cases, args.workers))
        except TierUnavailable as exc:
            print(f"\nembedding: SKIPPED ({exc})")
            report["tiers"]["embedding"] = {"skipped": str(exc)}

        try:
            runs = [judge_tier(cases, args.workers) for _ in range(args.repeat)]
            agree = agreement(runs)
            record("judge", runs[0], {
                "runs": args.repeat,
                "self_agreement": round(agree, 4),
                "accuracy_per_run": [round(accuracy(r), 4) for r in runs],
            })
            if args.repeat > 1:
                print(f"  self-agreement over {args.repeat} runs: {agree:.1%}; "
                      f"accuracy per run: {', '.join(f'{accuracy(r):.1%}' for r in runs)}")
        except TierUnavailable as exc:
            print(f"\njudge: SKIPPED ({exc})")
            report["tiers"]["judge"] = {"skipped": str(exc)}
        print(f"\nprovider time: {time.perf_counter() - started:.0f}s")

    if args.report:
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"report written to {args.report}")


if __name__ == "__main__":
    main()
