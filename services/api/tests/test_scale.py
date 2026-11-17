"""Trace queries stay fast with a realistic amount of data.

Seeds 50,000 traces in one project (cloned in SQL from a trace posted through the
API, so the stored shape is real), each with 10 steps (half a million rows in
spans), then times every query the dashboard makes.
The bound is generous for a shared CI runner; a query that loads every trace or
scans without an index takes seconds at this size and fails it.
"""

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.routes.traces as traces_route
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)

ROWS = 50_000
STEPS_PER_TRACE = 10
BOUND_SECONDS = 1.5


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


@pytest.fixture(scope="module")
def big_project():
    project = f"scale-{uuid4().hex[:8]}"
    seed = client.post(
        "/v1/traces",
        json={
            "project": {"project_id": project},
            "query": {"original": "How long do refunds take?"},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "Refunds take 5 to 7 business days."}]},
            "generation": {"model": "gpt-4o-mini", "answer": "Refunds take 5 to 7 business days."},
            "latency": {"total_ms": 900},
        },
    )
    assert seed.status_code == 202
    seed_id = seed.json()["trace_id"]

    with SessionLocal() as db:
        # Clone the seed: a fresh id per row, spread over 35 days, varied latency,
        # diagnosis and model, and every tenth row an attempt of a recovery run.
        db.execute(
            text(
                """
                INSERT INTO traces (trace_id, schema_version, project_id, environment, status,
                                    query_text, diagnosis_label, model_name, total_latency_ms,
                                    payload, created_at)
                SELECT n.id, t.schema_version, t.project_id, t.environment, t.status,
                       t.query_text || ' #' || g,
                       (ARRAY['healthy','retrieval_miss','unsupported_claim','wrong_answer'])[1 + g % 4],
                       (ARRAY['gpt-4o-mini','gpt-4.1'])[1 + g % 2],
                       (g * 37) % 4000,
                       jsonb_set(
                         CASE WHEN g % 10 = 0
                           THEN jsonb_set(t.payload, '{metadata}', jsonb_build_object(
                                  'recovery_run_id', 'run-' || (g / 30),
                                  'recovery_attempt', (g / 10) % 3 + 1))
                           ELSE t.payload END,
                         '{trace_id}', to_jsonb(n.id::text)),
                       now() - make_interval(secs => g * 60)
                FROM traces t
                CROSS JOIN generate_series(1, :rows) AS g
                CROSS JOIN LATERAL (SELECT gen_random_uuid() AS id, g AS k) AS n
                WHERE t.trace_id = :seed
                """
            ),
            {"rows": ROWS - 1, "seed": seed_id},
        )
        # Ten steps per cloned trace: an agent with nine children of mixed kinds.
        db.execute(
            text(
                """
                INSERT INTO spans (trace_id, span_id, parent_span_id, position, kind, name,
                                   status, started_at, ended_at, attributes)
                SELECT t.trace_id, 's' || g, CASE WHEN g = 1 THEN NULL ELSE 's1' END, g - 1,
                       (ARRAY['agent','llm','tool','retriever','chain'])[1 + g % 5], 'step ' || g,
                       'ok', t.created_at + make_interval(secs => g),
                       t.created_at + make_interval(secs => g + 1), '{}'::jsonb
                FROM traces t
                CROSS JOIN generate_series(1, :steps) AS g
                WHERE t.project_id = :project AND t.trace_id <> :seed
                """
            ),
            {"steps": STEPS_PER_TRACE, "project": project, "seed": seed_id},
        )
        db.execute(text("ANALYZE traces"))
        db.execute(text("ANALYZE spans"))
        db.commit()

    yield project

    with SessionLocal() as db:
        db.execute(text("DELETE FROM traces WHERE project_id = :p"), {"p": project})
        db.commit()


def _timed_get(path: str, params: dict) -> tuple[float, object]:
    client.get(path, params=params)  # warm the plan cache and connection pool
    start = time.perf_counter()
    response = client.get(path, params=params)
    elapsed = time.perf_counter() - start
    print(f"TIMING {path} {params.get('sort') or params.get('bucket') or ''}: {elapsed * 1000:.0f} ms")
    assert response.status_code == 200, response.text
    return elapsed, response


def test_the_project_really_holds_fifty_thousand_traces(big_project) -> None:
    with SessionLocal() as db:
        count = db.execute(text("SELECT count(*) FROM traces WHERE project_id = :p"), {"p": big_project}).scalar()
    assert count == ROWS


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"sort": "oldest"},
        {"sort": "slowest"},
        {"diagnosis": "retrieval_miss"},
        {"model": "gpt-4.1"},
        {"q": "refunds take"},
        {"since": "RECENT"},
    ],
    ids=["newest", "oldest", "slowest", "diagnosis", "model", "text", "since"],
)
def test_trace_list_pages_are_fast(big_project, params) -> None:
    query = {"project_id": big_project, "limit": 50, **params}
    if query.get("since") == "RECENT":
        query["since"] = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    elapsed, response = _timed_get("/v1/traces", query)
    assert len(response.json()) == 50
    assert elapsed < BOUND_SECONDS, f"{params}: {elapsed:.2f}s"

    # The next page, through the cursor, is just as quick.
    cursor = response.headers["X-Next-Cursor"]
    elapsed, response = _timed_get("/v1/traces", {**query, "cursor": cursor})
    assert len(response.json()) == 50
    assert elapsed < BOUND_SECONDS, f"{params} page 2: {elapsed:.2f}s"


def test_summary_and_time_series_are_fast(big_project) -> None:
    elapsed, response = _timed_get("/v1/metrics/summary", {"project_id": big_project})
    assert response.json()["total"] == ROWS
    assert elapsed < BOUND_SECONDS, f"summary: {elapsed:.2f}s"

    since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    elapsed, response = _timed_get(
        "/v1/metrics/timeseries", {"project_id": big_project, "since": since, "bucket": "day"}
    )
    assert sum(b["total"] for b in response.json()["buckets"]) > 40_000
    assert elapsed < BOUND_SECONDS, f"timeseries: {elapsed:.2f}s"


def test_the_project_really_holds_half_a_million_steps(big_project) -> None:
    with SessionLocal() as db:
        count = db.execute(
            text("SELECT count(*) FROM spans s JOIN traces t USING (trace_id) WHERE t.project_id = :p"),
            {"p": big_project},
        ).scalar()
    assert count >= (ROWS - 1) * STEPS_PER_TRACE


def test_a_trace_with_its_steps_is_fast(big_project) -> None:
    # The oldest: a clone with ten steps (the newest is the seed, with derived ones).
    oldest = client.get("/v1/traces", params={"project_id": big_project, "limit": 1, "sort": "oldest"}).json()[0]
    elapsed, response = _timed_get(f"/v1/traces/{oldest['trace_id']}", {})
    assert len(response.json()["steps"]) == STEPS_PER_TRACE
    assert elapsed < BOUND_SECONDS, f"trace with steps: {elapsed:.2f}s"


def test_recovery_runs_are_fast(big_project) -> None:
    elapsed, response = _timed_get("/v1/recovery-runs", {"project_id": big_project, "limit": 50})
    runs = response.json()
    assert len(runs) == 50
    assert all(run["attempts"] >= 1 for run in runs)
    assert elapsed < BOUND_SECONDS, f"recovery runs: {elapsed:.2f}s"
