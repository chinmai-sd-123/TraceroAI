"""Ingest hardening: server-owned fields, input limits, idempotency, body size,
request ids and the JSON 500."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app.api.routes.traces as traces_route
from app.db.models import TraceRecord
from app.db.session import SessionLocal
from app.main import app
from app.services.deep_evaluation import run_deep_evaluation
from app.services.trace_repository import TraceRepository
from tests.test_deep_groundedness import StubJudge

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_background_evaluation(monkeypatch):
    # Pretend the job was queued so no deep evaluation runs after the response;
    # these tests look at exactly what ingest stored.
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


def _payload(**overrides) -> dict:
    payload = {
        "query": {"original": "How long does a refund take?"},
        "retrieval": {
            "chunks": [
                {
                    "rank": 1,
                    "chunk_id": "c1",
                    "text": "Refunds are processed within 5 to 7 business days after approval.",
                }
            ]
        },
        "generation": {"model": "gpt-4o-mini", "answer": "It takes 5-7 business days once approved."},
    }
    payload.update(overrides)
    return payload


def _row_count(trace_id: str) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.count()).select_from(TraceRecord).where(TraceRecord.trace_id == UUID(trace_id))
        )


# --- server-owned fields ---


def test_client_cannot_supply_evaluations_feedback_or_diagnosis() -> None:
    payload = _payload(
        evaluations={"deep": [{"evaluator_name": "claim_groundedness", "label": "grounded", "score": 1.0}]},
        feedback=[{"rating": "thumbs_up", "comment": "forged", "created_at": "2001-01-01T00:00:00Z"}],
        diagnosis={"label": "healthy_answer", "reason": "trust me"},
    )

    trace_id = client.post("/v1/traces", json=payload).json()["trace_id"]
    stored = client.get(f"/v1/traces/{trace_id}").json()

    assert stored["evaluations"]["deep"] == []
    assert stored["feedback"] == []
    assert stored["diagnosis"]["reason"] != "trust me"


# --- input limits: a value that validates can always be stored ---


@pytest.mark.parametrize(
    "overrides",
    [
        {"project": {"project_id": "p" * 101}},
        {"project": {"environment": "e" * 51}},
        {"status": "s" * 51},
        {"generation": {"model": "m" * 101, "answer": "a"}},
        {
            "retrieval": {
                "chunks": [{"rank": i + 1, "chunk_id": str(i), "text": "t"} for i in range(201)]
            }
        },
    ],
    ids=["project_id", "environment", "status", "model", "chunk_count"],
)
def test_oversized_fields_are_rejected_with_422(overrides: dict) -> None:
    response = client.post("/v1/traces", json=_payload(**overrides))
    assert response.status_code == 422


def test_values_at_the_column_limits_are_stored() -> None:
    payload = _payload(
        project={"project_id": "p" * 100, "environment": "e" * 50},
        status="s" * 50,
        generation={"model": "m" * 100, "answer": "a"},
    )
    response = client.post("/v1/traces", json=payload)
    assert response.status_code == 202


def test_nul_characters_are_stripped_instead_of_failing_the_insert() -> None:
    payload = _payload(
        query={"original": "How long\x00 does a refund take?"},
        metadata={"ke\x00y": "val\x00ue"},
    )

    response = client.post("/v1/traces", json=payload)
    assert response.status_code == 202

    stored = client.get(f"/v1/traces/{response.json()['trace_id']}").json()
    assert stored["query"]["original"] == "How long does a refund take?"
    assert stored["metadata"] == {"key": "value"}


def test_eval_run_fields_are_limited_and_cleaned() -> None:
    run = {
        "run_type": "regression",
        "dataset": {"dataset_id": "d" * 101, "name": "set"},
        "pipeline": {"pipeline_version": "v1"},
        "summary": {"total_cases": 1, "passed_cases": 1, "failed_cases": 0},
        "cases": [{"case_id": "c1", "question": "q\x00?", "passed": True}],
    }
    assert client.post("/v1/eval-runs", json=run).status_code == 422

    run["dataset"]["dataset_id"] = "d" * 100
    response = client.post("/v1/eval-runs", json=run)
    assert response.status_code == 201
    stored = client.get(f"/v1/eval-runs/{response.json()['eval_run_id']}").json()
    assert stored["cases"][0]["question"] == "q?"


# --- idempotency on trace_id ---


def test_resending_a_trace_id_returns_the_stored_trace_without_a_duplicate() -> None:
    trace_id = str(uuid4())

    first = client.post("/v1/traces", json=_payload(trace_id=trace_id))
    second = client.post("/v1/traces", json=_payload(trace_id=trace_id))

    assert first.status_code == second.status_code == 202
    assert second.json()["trace_id"] == trace_id
    assert second.json()["message"] == "Trace already ingested."
    assert second.json()["diagnosis"] == first.json()["diagnosis"]
    assert _row_count(trace_id) == 1


def test_a_trace_id_from_another_project_is_a_conflict() -> None:
    trace_id = str(uuid4())
    client.post("/v1/traces", json=_payload(trace_id=trace_id, project={"project_id": "one"}))

    response = client.post(
        "/v1/traces", json=_payload(trace_id=trace_id, project={"project_id": "two"})
    )

    assert response.status_code == 409
    assert _row_count(trace_id) == 1


def test_concurrent_duplicate_insert_is_answered_from_the_stored_row(monkeypatch) -> None:
    # Two requests pass the "already stored?" check at the same time; the second
    # insert hits the primary key. Simulated by hiding the row from that check.
    trace_id = str(uuid4())
    client.post("/v1/traces", json=_payload(trace_id=trace_id))

    real_get = TraceRepository.get
    calls = {"n": 0}

    def get_missing_once(self, tid):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_get(self, tid)

    monkeypatch.setattr(TraceRepository, "get", get_missing_once)
    response = client.post("/v1/traces", json=_payload(trace_id=trace_id))

    assert response.status_code == 202
    assert response.json()["message"] == "Trace already ingested."
    assert _row_count(trace_id) == 1


# --- synchronous deep evaluation ---


def test_sync_deep_eval_returns_the_judges_diagnosis(monkeypatch) -> None:
    # The lexical pass labels this correct paraphrase a retrieval miss; the judge
    # (stubbed: everything relevant and grounded) says it's healthy. The response
    # must carry the judge's verdict, which is what the recovery agent routes on.
    monkeypatch.setattr(
        traces_route,
        "run_deep_evaluation",
        lambda trace_id, **kwargs: run_deep_evaluation(trace_id, judge=StubJudge(), **kwargs),
    )

    quick = client.post("/v1/traces", json=_payload()).json()["diagnosis"]["label"]
    judged = client.post("/v1/traces?sync_deep_eval=true", json=_payload()).json()

    assert quick != "healthy_answer"
    assert judged["diagnosis"]["label"] == "healthy_answer"


# --- request body size ---


def test_body_over_the_limit_is_rejected_with_413() -> None:
    payload = _payload(metadata={"blob": "x" * 1_100_000})
    response = client.post("/v1/traces", json=payload)
    assert response.status_code == 413


def test_chunked_body_over_the_limit_is_rejected_with_413() -> None:
    def chunks():
        for _ in range(12):
            yield b"x" * 100_000

    response = client.post(
        "/v1/traces", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_chunked_body_under_the_limit_is_processed() -> None:
    import json

    body = json.dumps(_payload()).encode()

    def chunks():
        yield body[:20]
        yield body[20:]

    response = client.post(
        "/v1/traces", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 202


# --- request ids and the JSON 500 ---


def test_every_response_carries_a_request_id() -> None:
    generated = client.get("/health")
    assert len(generated.headers["X-Request-ID"]) == 32

    echoed = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["X-Request-ID"] == "abc-123"

    unsafe = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert unsafe.headers["X-Request-ID"] != "bad id\twith spaces"


def test_unhandled_error_is_a_json_500_with_the_request_id(monkeypatch) -> None:
    def boom(self, project_id=None):
        raise RuntimeError("database fell over")

    monkeypatch.setattr(TraceRepository, "list", boom)

    response = client.get("/v1/traces", headers={"X-Request-ID": "trace-me"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error.", "request_id": "trace-me"}
    assert response.headers["X-Request-ID"] == "trace-me"
    assert "fell over" not in response.text
