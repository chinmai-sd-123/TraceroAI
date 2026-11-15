"""Recovery runs: the attempts a RecoveryAgent run recorded, grouped by run id."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.routes.traces as traces_route
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


@pytest.fixture
def project() -> str:
    return f"recovery-{uuid4().hex[:8]}"


def _attempt(project: str, run_id: str, attempt: int, *, question: str = "What is the refund window?",
             action: str | None = None, top_k: int = 4) -> str:
    response = client.post(
        "/v1/traces",
        json={
            "project": {"project_id": project},
            "query": {"original": question},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "Refunds within 30 days."}]},
            "generation": {"model": "gpt-4o-mini", "answer": "Refunds are possible within 30 days."},
            "metadata": {
                "agent": "recovery",
                "recovery_run_id": run_id,
                "attempt": attempt,
                "recovery_action": action,
                "top_k": top_k,
            },
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["trace_id"]


def test_runs_group_attempts_in_order(project) -> None:
    run_a, run_b = uuid4().hex, uuid4().hex
    first = _attempt(project, run_a, 1)
    second = _attempt(project, run_a, 2, action="bump_retrieval", top_k=6)
    only = _attempt(project, run_b, 1, question="Is there phone support?")
    client.post(
        "/v1/traces",
        json={
            "project": {"project_id": project},
            "query": {"original": "not a recovery run"},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "x"}]},
            "generation": {"model": "m", "answer": "y"},
        },
    )

    runs = client.get("/v1/recovery-runs", params={"project_id": project}).json()

    assert {r["run_id"] for r in runs} == {run_a, run_b}
    a = next(r for r in runs if r["run_id"] == run_a)
    assert a["question"] == "What is the refund window?"
    assert a["attempts"] == 2
    assert a["trace_ids"] == [first, second]
    assert a["actions"] == [None, "bump_retrieval"]
    assert a["top_k"] == [4, 6]
    assert a["first_diagnosis"] and a["final_diagnosis"]
    b = next(r for r in runs if r["run_id"] == run_b)
    assert b["trace_ids"] == [only]


def test_traces_filter_by_recovery_run(project) -> None:
    run = uuid4().hex
    ids = {_attempt(project, run, 1), _attempt(project, run, 2, action="tighten_generation")}
    _attempt(project, uuid4().hex, 1)

    listed = client.get("/v1/traces", params={"recovery_run_id": run}).json()

    assert {t["trace_id"] for t in listed} == ids


def test_run_list_limit_is_bounded() -> None:
    assert client.get("/v1/recovery-runs", params={"limit": 0}).status_code == 422
    assert client.get("/v1/recovery-runs", params={"limit": 201}).status_code == 422
