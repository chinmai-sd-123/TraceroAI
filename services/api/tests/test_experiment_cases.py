"""Experiments can carry their per-question results, each tied to a variant."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _experiment(cases: list[dict], *, a=(1, 1), b=(2, 0)) -> dict:
    total = a[0] + a[1] + b[0] + b[1]
    passed = a[0] + b[0]
    return {
        "eval_run_id": str(uuid4()),
        "run_type": "experiment",
        "project": {"project_id": f"exp-{uuid4().hex[:8]}"},
        "dataset": {"dataset_id": "refunds", "name": "Refund questions"},
        "pipeline": {"pipeline_version": "top_k comparison"},
        "summary": {"total_cases": total, "passed_cases": passed, "failed_cases": total - passed},
        "variants": [
            {"variant_id": "k2", "name": "top_k=2", "passed_cases": a[0], "failed_cases": a[1]},
            {"variant_id": "k4", "name": "top_k=4", "passed_cases": b[0], "failed_cases": b[1]},
        ],
        "cases": cases,
    }


def _case(variant: str, case_id: str, passed: bool) -> dict:
    return {"variant_id": variant, "case_id": case_id, "question": f"question {case_id}", "passed": passed}


def test_an_experiment_stores_its_cases_by_variant() -> None:
    body = _experiment(
        [_case("k2", "q1", True), _case("k2", "q2", False), _case("k4", "q1", True), _case("k4", "q2", True)]
    )
    assert client.post("/v1/eval-runs", json=body).status_code == 201

    stored = client.get(f"/v1/eval-runs/{body['eval_run_id']}").json()
    assert [(c["variant_id"], c["case_id"], c["passed"]) for c in stored["cases"]] == [
        ("k2", "q1", True), ("k2", "q2", False), ("k4", "q1", True), ("k4", "q2", True),
    ]


def test_experiments_without_cases_still_work() -> None:
    assert client.post("/v1/eval-runs", json=_experiment([])).status_code == 201


def test_a_case_must_name_a_variant_of_the_run() -> None:
    body = _experiment([_case("k9", "q1", True)], a=(0, 0), b=(0, 0))
    body["summary"] = {"total_cases": 0, "passed_cases": 0, "failed_cases": 0}
    body["variants"][0].update(passed_cases=0, failed_cases=0)
    assert client.post("/v1/eval-runs", json=body).status_code == 422

    missing = _experiment([{**_case("k2", "q1", True), "variant_id": None}])
    assert client.post("/v1/eval-runs", json=missing).status_code == 422


def test_case_results_must_match_the_variant_counts() -> None:
    # k2 claims 1 passed and 1 failed, but its cases say 2 passed.
    body = _experiment([_case("k2", "q1", True), _case("k2", "q2", True)])
    assert client.post("/v1/eval-runs", json=body).status_code == 422
