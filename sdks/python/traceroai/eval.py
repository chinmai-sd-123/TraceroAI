"""Client-usable RAG experiment harness.

You bring a dataset of (question, expected_answer) cases and your own
retrieve()/generate() functions; this runs your pipeline across one or more
config variants, grades each answer with TraceroAI's server-side judge
(/v1/eval/grade — the single source of truth), picks the best variant, and posts
the result to /v1/eval-runs so it shows on your project's dashboard.

    from traceroai import TraceroClient
    from traceroai.eval import run_experiment, Case, Variant

    run_experiment(
        client=TraceroClient(base_url=..., api_key=...),
        dataset=[Case("q1", "How long does a refund take?", "5-7 business days.")],
        retrieve=my_retrieve,     # (query, top_k) -> list[chunk dict]
        generate=my_generate,     # (query, context) -> answer str
        variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
        project_id="my-app",
    )

The harness is pure orchestration over httpx — no LLM key or judge code lives in
the SDK; the server grades.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from traceroai.client import TraceroClient

RetrieveFn = Callable[[str, int], list[dict[str, Any]]]
GenerateFn = Callable[[str, str], str]


@dataclass(frozen=True)
class Case:
    case_id: str
    question: str
    expected_answer: str


@dataclass(frozen=True)
class Variant:
    variant_id: str
    name: str
    top_k: int = 3
    extra: dict[str, Any] = field(default_factory=dict)

    def as_config(self) -> dict[str, Any]:
        return {"top_k": self.top_k, **self.extra}


@dataclass
class ExperimentResult:
    eval_run_id: str | None
    recommendation: str
    variants: list[dict[str, Any]]


def _grade(client: TraceroClient, question: str, expected: str, actual: str) -> bool | None:
    """Grade one answer via the server. Returns True/False, or None if the case
    could not be graded (judge unavailable / error) — never a fabricated score."""
    headers = {}
    if client.api_key:
        headers["Authorization"] = f"Bearer {client.api_key}"
    try:
        resp = httpx.post(
            f"{client.base_url}/v1/eval/grade",
            json={"question": question, "expected": expected, "actual": actual},
            headers=headers,
            timeout=client.timeout_seconds * 3,  # grading is an LLM call
        )
        if resp.status_code != 200:
            return None
        return bool(resp.json().get("correct"))
    except Exception:
        return None


def _format_context(chunks: list[dict[str, Any]]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.get('text', '')}" for i, c in enumerate(chunks))


def _run_variant(
    client: TraceroClient,
    dataset: list[Case],
    variant: Variant,
    retrieve: RetrieveFn,
    generate: GenerateFn,
) -> dict[str, Any]:
    correct = 0
    gradeable = 0
    latencies: list[int] = []

    for case in dataset:
        start = time.perf_counter()
        chunks = retrieve(case.question, variant.top_k)
        answer = generate(case.question, _format_context(chunks))
        latencies.append(int((time.perf_counter() - start) * 1000))

        verdict = _grade(client, case.question, case.expected_answer, answer)
        if verdict is None:
            continue  # ungradeable — excluded from accuracy, not counted wrong
        gradeable += 1
        if verdict:
            correct += 1

    accuracy = round(correct / gradeable, 3) if gradeable else 0.0
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0
    ungradeable = len(dataset) - gradeable

    return {
        "variant_id": variant.variant_id,
        "name": variant.name,
        "config": {**variant.as_config(), "ungradeable_cases": ungradeable},
        "passed_cases": correct,
        "failed_cases": gradeable - correct,
        "average_latency_ms": avg_latency,
        "metrics": [{"metric_name": "accuracy", "score": accuracy}],
        "_accuracy": accuracy,  # internal, for winner selection
    }


def run_experiment(
    *,
    client: TraceroClient,
    dataset: list[Case],
    retrieve: RetrieveFn,
    generate: GenerateFn,
    variants: list[Variant],
    project_id: str = "experiments",
    dataset_name: str = "Custom dataset",
    post: bool = True,
) -> ExperimentResult:
    """Run the experiment and (by default) post the eval-run to the dashboard."""
    if len(variants) < 2:
        raise ValueError("An experiment needs at least two variants to compare.")
    if not dataset:
        raise ValueError("The dataset is empty.")

    results = [_run_variant(client, dataset, v, retrieve, generate) for v in variants]

    # Guard the all-ungradeable case: if NO variant had a single gradeable case (judge
    # down for the whole run), there's no honest winner — don't fabricate one.
    gradeable_per_variant = [
        r["passed_cases"] + r["failed_cases"] for r in results
    ]
    if not any(gradeable_per_variant):
        recommendation = (
            "No variant could be scored — the grading judge was unavailable for every "
            "case. Configure the judge (TRACEROAI_OPENAI_API_KEY) and re-run."
        )
        winner = results[0]  # arbitrary; recommendation makes the situation explicit
    else:
        # Winner: highest accuracy, tie-break on lower latency. Variants with zero
        # gradeable cases sort last (accuracy 0.0) so they can't win over a scored one.
        winner = max(
            results,
            key=lambda r: (
                (r["passed_cases"] + r["failed_cases"]) > 0,  # scored variants first
                r["_accuracy"],
                -r["average_latency_ms"],
            ),
        )
        recommendation = (
            f"Variant '{winner['name']}' ({winner['variant_id']}) wins with "
            f"accuracy={winner['_accuracy']:.2f} over "
            f"{winner['passed_cases'] + winner['failed_cases']} graded case(s)."
        )

    # Strip internal fields before sending.
    variants_payload = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    win_total = winner["passed_cases"] + winner["failed_cases"]

    payload = {
        "run_type": "experiment",
        "status": "completed",
        "project": {"project_id": project_id},
        "dataset": {"dataset_id": dataset_name.lower().replace(" ", "_"), "name": dataset_name},
        "pipeline": {"pipeline_version": "sdk_experiment_harness_v1"},
        "summary": {
            "total_cases": win_total,
            "passed_cases": winner["passed_cases"],
            "failed_cases": winner["failed_cases"],
            "pass_rate": round(winner["passed_cases"] / win_total, 3) if win_total else 0.0,
            "recommendation": recommendation,
        },
        "variants": variants_payload,
    }

    eval_run_id: str | None = None
    if post:
        headers = {"Content-Type": "application/json"}
        if client.api_key:
            headers["Authorization"] = f"Bearer {client.api_key}"
        resp = httpx.post(
            f"{client.base_url}/v1/eval-runs",
            json=payload,
            headers=headers,
            timeout=client.timeout_seconds,
        )
        resp.raise_for_status()
        eval_run_id = resp.json().get("eval_run_id")

    return ExperimentResult(
        eval_run_id=eval_run_id,
        recommendation=recommendation,
        variants=variants_payload,
    )
