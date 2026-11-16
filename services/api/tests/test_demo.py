"""The first-run demo data: valid, idempotent, spread over a week, removable."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.routes.traces as traces_route
from app.db.session import SessionLocal
from app.demo import DEMO_PROJECT, load_recorded, remove, seed, spread_over_last_week
from app.main import app
from app.schemas.eval_runs import EvalRunIngestRequest
from app.schemas.traces import TraceIngestRequest

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


@pytest.fixture
def clean_demo():
    with SessionLocal() as db:
        remove(db)
    yield
    with SessionLocal() as db:
        remove(db)


def test_recorded_runs_are_valid_ingest_payloads() -> None:
    recorded = load_recorded()
    traces = recorded["traces"]
    assert len(traces) >= 30
    for trace in traces:
        parsed = TraceIngestRequest.model_validate(trace)
        assert parsed.project.project_id == DEMO_PROJECT
        assert "diagnosis" not in trace and "evaluations" not in trace  # the server computes these
    assert len({t["trace_id"] for t in traces}) == len(traces)
    experiment = EvalRunIngestRequest.model_validate(recorded["experiment"])
    assert experiment.project.project_id == DEMO_PROJECT


def test_seeding_diagnoses_every_trace_and_is_idempotent(clean_demo) -> None:
    total = len(load_recorded()["traces"])

    first = seed(client, wait_seconds=5)
    assert (first.sent, first.already_there, first.diagnosed) == (total, 0, total)
    assert first.experiment == "sent"

    second = seed(client, wait_seconds=5)
    assert (second.sent, second.already_there) == (0, total)
    assert second.experiment == "already there"

    with SessionLocal() as db:
        stored = db.execute(text("SELECT count(*) FROM traces WHERE project_id = :p"), {"p": DEMO_PROJECT}).scalar()
    assert stored == total


def test_spread_puts_traces_in_the_past_week_and_keeps_runs_together(clean_demo) -> None:
    seed(client, wait_seconds=5)
    now = datetime.now(UTC)
    with SessionLocal() as db:
        moved = spread_over_last_week(db, now=now)
        rows = db.execute(
            text("SELECT trace_id::text, created_at, payload->'metadata' FROM traces WHERE project_id = :p"),
            {"p": DEMO_PROJECT},
        ).all()
    assert moved == len(rows)
    # All inside the overview's "last 7 days".
    assert all(now - timedelta(days=7) < at <= now for _, at, _ in rows)
    # The trace's own timestamp (what lists show) moved with it.
    for trace_id, at, _ in rows:
        shown = datetime.fromisoformat(client.get(f"/v1/traces/{trace_id}").json()["timestamp"])
        assert abs(shown - at) < timedelta(seconds=1)
    # More than one day has traces, so the overview's chart has shape.
    assert len({at.date() for _, at, _ in rows}) >= 5

    by_run: dict[str, list[tuple[int, datetime]]] = {}
    for _, at, metadata in rows:
        if metadata and metadata.get("recovery_run_id"):
            by_run.setdefault(metadata["recovery_run_id"], []).append((int(metadata["attempt"]), at))
    assert by_run
    for attempts in by_run.values():
        attempts.sort()
        times = [at for _, at in attempts]
        assert times == sorted(times)  # attempt order is preserved
        assert times[-1] - times[0] <= timedelta(minutes=len(times))


def test_remove_deletes_the_demo_project_only(clean_demo) -> None:
    other = client.post(
        "/v1/traces",
        json={
            "project": {"project_id": "not-demo"},
            "query": {"original": "keep me"},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "text"}]},
            "generation": {"model": "m", "answer": "answer"},
        },
    ).json()["trace_id"]
    seed(client, wait_seconds=5)
    with SessionLocal() as db:
        traces, runs = remove(db)
    assert traces == len(load_recorded()["traces"])
    assert runs == 1
    assert client.get(f"/v1/traces/{other}").status_code == 200
