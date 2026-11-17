"""Steps: a trace is a summary row plus a tree of steps (docs/adr/0002)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.routes.traces as traces_route
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)

T0 = datetime(2026, 11, 17, 9, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


def _rag(**extra) -> dict:
    return {
        "project": {"project_id": f"steps-{uuid4().hex[:8]}"},
        "timestamp": T0.isoformat(),
        "query": {"original": "How long do refunds take?"},
        "retrieval": {
            "strategy": "vector",
            "config": {"final_top_k": 2},
            "chunks": [
                {"rank": 1, "chunk_id": "c1", "text": "Refunds take 5 to 7 business days."},
                {"rank": 2, "chunk_id": "c2", "text": "Refunds go to the original card."},
            ],
        },
        "prompt": {"version": "grounded_v1"},
        "generation": {
            "model": "gpt-4o-mini",
            "answer": "Refunds take 5 to 7 business days.",
            "usage": {"prompt_tokens": 120, "completion_tokens": 12},
        },
        "latency": {"retrieval_ms": 200, "prompt_build_ms": 5, "generation_ms": 900, "total_ms": 1110},
        **extra,
    }


def _at(ms: int) -> str:
    return (T0 + timedelta(milliseconds=ms)).isoformat()


# An agent: it plans, calls a tool, then answers with a second model call.
AGENT_STEPS = [
    {"step_id": "a", "kind": "agent", "name": "support agent", "started_at": _at(0), "ended_at": _at(2400),
     "input": {"question": "Where is my refund?"}, "output": {"answer": "It was issued on Monday."}},
    {"step_id": "a.1", "parent_id": "a", "kind": "llm", "name": "gpt-4o-mini", "started_at": _at(10),
     "ended_at": _at(810), "output": {"tool_call": "lookup_refund"}, "attributes": {"prompt_tokens": 300}},
    {"step_id": "a.2", "parent_id": "a", "kind": "tool", "name": "lookup_refund", "started_at": _at(820),
     "ended_at": _at(1300), "input": {"order": "A-17"}, "output": {"issued": "2026-11-16"}},
    {"step_id": "a.2.1", "parent_id": "a.2", "kind": "retriever", "name": "orders index", "started_at": _at(830),
     "ended_at": _at(1100), "status": "error", "status_message": "timeout, retried"},
    {"step_id": "a.3", "parent_id": "a", "kind": "llm", "name": "gpt-4o-mini", "started_at": _at(1310),
     "ended_at": _at(2390)},
]


def test_a_flat_rag_trace_gets_steps_derived_from_it() -> None:
    trace_id = client.post("/v1/traces", json=_rag()).json()["trace_id"]
    steps = client.get(f"/v1/traces/{trace_id}").json()["steps"]

    assert [(s["step_id"], s["parent_id"], s["kind"]) for s in steps] == [
        ("run", None, "chain"),
        ("retrieval", "run", "retriever"),
        ("prompt", "run", "chain"),
        ("generation", "run", "llm"),
    ]
    by_id = {s["step_id"]: s for s in steps}
    # Timed one after another from the latencies the client measured.
    assert [by_id[k]["duration_ms"] for k in ("run", "retrieval", "prompt", "generation")] == [1110, 200, 5, 900]
    assert by_id["prompt"]["started_at"] == by_id["retrieval"]["ended_at"]
    assert by_id["retrieval"]["output"] == {"chunk_ids": ["c1", "c2"]}
    assert by_id["generation"]["attributes"]["prompt_tokens"] == 120
    assert by_id["prompt"]["attributes"] == {"version": "grounded_v1"}


def test_a_nested_agent_run_round_trips() -> None:
    trace_id = client.post("/v1/traces", json=_rag(steps=AGENT_STEPS)).json()["trace_id"]
    steps = client.get(f"/v1/traces/{trace_id}").json()["steps"]

    assert [s["step_id"] for s in steps] == ["a", "a.1", "a.2", "a.2.1", "a.3"]  # in the order sent
    for sent, got in zip(AGENT_STEPS, steps, strict=True):
        assert got["parent_id"] == sent.get("parent_id")
        assert got["kind"] == sent["kind"]
        assert got["name"] == sent["name"]
        assert got["input"] == sent.get("input")
        assert got["output"] == sent.get("output")
        assert got["attributes"] == sent.get("attributes", {})
        assert got["status"] == sent.get("status", "ok")
    assert steps[3]["status_message"] == "timeout, retried"
    assert [s["duration_ms"] for s in steps] == [2400, 800, 480, 270, 1080]


@pytest.mark.parametrize(
    ("steps", "problem"),
    [
        ([AGENT_STEPS[0], AGENT_STEPS[0]], "more than once"),
        ([AGENT_STEPS[1]], "isn't in the trace"),
        (
            [
                {"step_id": "x", "parent_id": "y", "kind": "chain", "name": "x", "started_at": _at(0)},
                {"step_id": "y", "parent_id": "x", "kind": "chain", "name": "y", "started_at": _at(0)},
            ],
            "its own ancestor",
        ),
        ([{"step_id": "z", "kind": "tool", "name": "z", "started_at": _at(10), "ended_at": _at(5)}], "ends before"),
        ([{"step_id": "k", "kind": "database", "name": "k", "started_at": _at(0)}], "kind"),
    ],
    ids=["duplicate id", "missing parent", "loop", "ends before start", "unknown kind"],
)
def test_steps_that_are_not_a_tree_are_rejected(steps, problem) -> None:
    response = client.post("/v1/traces", json=_rag(steps=steps))
    assert response.status_code == 422
    assert problem in response.text


def test_steps_stay_out_of_lists_and_the_stored_trace_document() -> None:
    body = _rag(steps=AGENT_STEPS)
    trace_id = client.post("/v1/traces", json=body).json()["trace_id"]

    listed = client.get("/v1/traces", params={"project_id": body["project"]["project_id"]}).json()
    assert [t["trace_id"] for t in listed] == [trace_id]
    assert "steps" not in listed[0]
    with SessionLocal() as db:
        payload = db.execute(text("SELECT payload FROM traces WHERE trace_id = :t"), {"t": trace_id}).scalar()
        count = db.execute(text("SELECT count(*) FROM spans WHERE trace_id = :t"), {"t": trace_id}).scalar()
    assert "steps" not in payload
    assert count == len(AGENT_STEPS)


def test_deleting_a_trace_deletes_its_steps() -> None:
    trace_id = client.post("/v1/traces", json=_rag(steps=AGENT_STEPS)).json()["trace_id"]
    assert client.delete(f"/v1/traces/{trace_id}").status_code == 204
    with SessionLocal() as db:
        count = db.execute(text("SELECT count(*) FROM spans WHERE trace_id = :t"), {"t": trace_id}).scalar()
    assert count == 0


def test_a_trace_stored_before_steps_existed_gets_them_on_read() -> None:
    trace_id = client.post("/v1/traces", json=_rag()).json()["trace_id"]
    with SessionLocal() as db:  # as if stored before migration 0008
        db.execute(text("DELETE FROM spans WHERE trace_id = :t"), {"t": trace_id})
        db.commit()
    steps = client.get(f"/v1/traces/{trace_id}").json()["steps"]
    assert [s["step_id"] for s in steps] == ["run", "retrieval", "prompt", "generation"]
    assert steps[0]["duration_ms"] == 1110


def test_resending_a_trace_does_not_duplicate_its_steps() -> None:
    body = _rag(steps=AGENT_STEPS, trace_id=str(uuid4()))
    assert client.post("/v1/traces", json=body).status_code == 202
    assert client.post("/v1/traces", json=body).status_code == 202
    with SessionLocal() as db:
        count = db.execute(text("SELECT count(*) FROM spans WHERE trace_id = :t"), {"t": body["trace_id"]}).scalar()
    assert count == len(AGENT_STEPS)
