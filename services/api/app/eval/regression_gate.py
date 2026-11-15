from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.eval.constructed_cases import build_cases
from app.schemas.traces import Trace
from app.services.quick_evaluation import run_quick_evaluation

GOLDEN_PATH = Path(__file__).parent / "golden_traces.json"


@dataclass
class CaseResult:
    case_id: str
    expected: str
    actual: str
    passed: bool


@dataclass
class GateReport:
    results: list[CaseResult]

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        passed = sum(1 for result in self.results if result.passed)
        return passed / len(self.results)

    @property
    def failures(self) -> list[CaseResult]:
        return [result for result in self.results if not result.passed]


def load_golden_cases(path: Path = GOLDEN_PATH, *, constructed: bool = True) -> list[dict]:
    """The hand-labelled cases in golden_traces.json, plus (by default) the
    cases built and labelled in constructed_cases.py."""
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    if constructed:
        cases = cases + build_cases()
    return cases


def run_regression_gate(cases: list[dict] | None = None) -> GateReport:
    if cases is None:
        cases = load_golden_cases()

    results: list[CaseResult] = []
    for case in cases:
        trace = Trace(**case["trace"])
        # Lexical only: deterministic and offline, so the gate gives the same
        # answer in CI as on a laptop with an embeddings key.
        evaluated = run_quick_evaluation(trace, semantic=False)

        actual = evaluated.diagnosis.label
        expected = case["expected_diagnosis"]
        results.append(
            CaseResult(
                case_id=case["case_id"],
                expected=expected,
                actual=actual,
                passed=actual == expected,
            )
        )

    return GateReport(results=results)
