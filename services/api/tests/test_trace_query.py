"""Paginated, filtered trace listing and the SQL summary."""

from datetime import UTC, datetime, timedelta
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
    return f"query-{uuid4().hex[:8]}"


def _post(project: str, query: str, *, model: str = "gpt-4o-mini", total_ms: int = 100,
          answer: str = "Refunds take 5 to 7 business days.", tokens: int | None = None) -> str:
    generation = {"model": model, "answer": answer}
    if tokens is not None:
        generation["usage"] = {"prompt_tokens": tokens, "completion_tokens": 0}
    response = client.post(
        "/v1/traces",
        json={
            "project": {"project_id": project},
            "query": {"original": query},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "Refunds take 5 to 7 business days."}]},
            "generation": generation,
            "latency": {"total_ms": total_ms},
        },
    )
    assert response.status_code == 202
    return response.json()["trace_id"]


def _ids(response) -> list[str]:
    return [t["trace_id"] for t in response.json()]


def test_pages_cover_every_trace_once_newest_first(project) -> None:
    posted = [_post(project, f"question {i}") for i in range(5)]

    seen: list[str] = []
    cursor = None
    pages = 0
    while True:
        params = {"project_id": project, "limit": 2, **({"cursor": cursor} if cursor else {})}
        response = client.get("/v1/traces", params=params)
        assert response.status_code == 200
        seen += _ids(response)
        pages += 1
        cursor = response.headers.get("X-Next-Cursor")
        if not cursor:
            break

    assert pages == 3
    # Every trace exactly once, in the same order as one unpaged request. (Not
    # necessarily reverse posting order: two inserts can share a timestamp, and
    # the database clock may step back, so ties fall back to the trace id.)
    assert len(seen) == len(set(seen)) == 5
    assert set(seen) == set(posted)
    unpaged = client.get("/v1/traces", params={"project_id": project, "limit": 200})
    assert seen == _ids(unpaged)


def test_a_bad_cursor_is_a_400(project) -> None:
    response = client.get("/v1/traces", params={"project_id": project, "cursor": "nonsense!"})
    assert response.status_code == 400


def test_limit_is_bounded() -> None:
    assert client.get("/v1/traces", params={"limit": 201}).status_code == 422
    assert client.get("/v1/traces", params={"limit": 0}).status_code == 422


def test_filters(project) -> None:
    refund = _post(project, "How long do REFUNDS take?")
    _post(project, "What plans exist?", model="other-model")
    percent = _post(project, "Is there a 100% guarantee?")

    def ids(**params):
        return _ids(client.get("/v1/traces", params={"project_id": project, **params}))

    assert ids(q="refunds") == [refund]  # case-insensitive substring
    assert ids(q="100%") == [percent]  # % is matched literally
    assert ids(q="_") == []  # and so is _
    assert len(ids(model="gpt-4o-mini")) == 2
    diagnosis = client.get(f"/v1/traces/{refund}").json()["diagnosis"]["label"]
    assert refund in ids(diagnosis=diagnosis)

    future = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    assert ids(since=future) == []
    assert len(ids(until=future)) == 3


def test_summary_is_computed_over_every_trace(project) -> None:
    _post(project, "a", total_ms=100, tokens=1000)
    _post(project, "b", total_ms=300)
    _post(project, "c", total_ms=0)  # not measured: excluded from latency

    summary = client.get("/v1/metrics/summary", params={"project_id": project}).json()

    assert summary["total"] == 3
    assert sum(summary["by_diagnosis"].values()) == 3
    assert summary["by_source"] == {"lexical": 3}
    assert summary["latency_ms"]["measured"] == 2
    assert summary["latency_ms"]["avg"] == 200
    assert summary["latency_ms"]["p95"] == 290  # interpolated between 100 and 300
    assert summary["cost_usd"]["priced"] == 1  # only the trace with tokens has a price
    assert summary["cost_usd"]["total"] == pytest.approx(0.00015)


def test_summary_of_an_empty_project(project) -> None:
    summary = client.get("/v1/metrics/summary", params={"project_id": project}).json()
    assert summary["total"] == 0
    assert summary["latency_ms"] == {"measured": 0, "avg": None, "p50": None, "p95": None}
    assert summary["cost_usd"]["avg"] is None
