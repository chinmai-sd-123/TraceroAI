"""Readiness checks and Prometheus metrics."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.routes.health as health
import app.api.routes.traces as traces_route
from app.core.config import get_settings
from app.core.metrics import register_queue_collector
from app.main import app
from tests.test_deep_groundedness import make_trace_payload

client = TestClient(app)


def _metric(name: str, **labels) -> float:
    """Current value of one sample from /metrics."""
    wanted = ",".join(f'{k}="{v}"' for k, v in labels.items())
    for line in client.get("/metrics").text.splitlines():
        if line.startswith(f"{name}{{{wanted}}} ") or (not labels and line.startswith(f"{name} ")):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def test_ready_when_the_database_answers() -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "not_configured"},
    }


def test_not_ready_without_the_database_and_nothing_leaks(monkeypatch) -> None:
    class Down:
        def connect(self):
            raise RuntimeError("could not connect to db.internal:5432 as admin:hunter2")

    monkeypatch.setattr(health, "engine", Down())

    ready = client.get("/health/ready")
    db = client.get("/health/db")

    assert ready.status_code == db.status_code == 503
    assert ready.json()["checks"]["database"] == "unavailable"
    for response in (ready, db):
        assert "hunter2" not in response.text and "db.internal" not in response.text


def test_not_ready_when_a_configured_redis_is_down(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "redis_url", "redis://127.0.0.1:1/0")
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "unavailable"


def test_requests_are_counted_by_route_template(monkeypatch) -> None:
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]
    before = _metric(
        "traceroai_http_requests_total", method="GET", route="/v1/traces/{trace_id}", status="200"
    )

    client.get(f"/v1/traces/{trace_id}")

    after = _metric(
        "traceroai_http_requests_total", method="GET", route="/v1/traces/{trace_id}", status="200"
    )
    assert after == before + 1
    assert trace_id not in client.get("/metrics").text  # ids never become labels


def test_unknown_paths_share_one_label() -> None:
    before = _metric("traceroai_http_requests_total", method="GET", route="unmatched", status="404")
    client.get("/no/such/path/123")
    client.get("/another/unknown")
    after = _metric("traceroai_http_requests_total", method="GET", route="unmatched", status="404")
    assert after == before + 2


def test_ingest_outcomes_are_counted(monkeypatch) -> None:
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)
    stored = _metric("traceroai_traces_ingested_total", outcome="stored")
    duplicate = _metric("traceroai_traces_ingested_total", outcome="duplicate")

    payload = make_trace_payload() | {"trace_id": str(uuid4())}  # new each run
    client.post("/v1/traces", json=payload)
    client.post("/v1/traces", json=payload)

    assert _metric("traceroai_traces_ingested_total", outcome="stored") >= stored + 1
    assert _metric("traceroai_traces_ingested_total", outcome="duplicate") >= duplicate + 1


def test_queue_depth_is_exported() -> None:
    register_queue_collector()
    text = client.get("/metrics").text
    assert "traceroai_queue_redis_connected 0.0" in text
    assert 'traceroai_queue_jobs{state="queued"} 0.0' in text


class TestMetricsAccess:
    @pytest.fixture(autouse=True)
    def _keys(self, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "require_api_key", True)
        monkeypatch.setattr(settings, "admin_api_keys", ["key_admin"])
        monkeypatch.setattr(settings, "project_api_keys", {"key_acme": "acme"})

    def test_only_an_admin_key_may_read_metrics_when_keys_are_required(self) -> None:
        assert client.get("/metrics").status_code == 401
        assert (
            client.get("/metrics", headers={"Authorization": "Bearer key_acme"}).status_code
            == 401
        )
        assert (
            client.get("/metrics", headers={"Authorization": "Bearer key_admin"}).status_code
            == 200
        )

    def test_health_checks_stay_open(self) -> None:
        assert client.get("/health").status_code == 200
        assert client.get("/health/ready").status_code == 200


def test_database_connections_time_out() -> None:
    from app.db.session import engine_options

    settings = get_settings()
    assert engine_options(settings)["connect_args"] == {
        "connect_timeout": settings.db_connect_timeout_seconds
    }


def test_readiness_answers_quickly_when_the_database_host_drops_packets(monkeypatch) -> None:
    # 10.255.255.1 is unroutable: packets are dropped rather than refused. Before
    # the connect timeout this check could hang for the OS TCP timeout.
    import time

    from sqlalchemy import create_engine

    from app.core.config import Settings
    from app.db.session import engine_options

    options = engine_options(Settings(_env_file=None, db_connect_timeout_seconds=2))
    blackholed = create_engine(
        "postgresql+psycopg://user:secret@10.255.255.1:5432/db", **options
    )
    monkeypatch.setattr(health, "engine", blackholed)

    started = time.perf_counter()
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert time.perf_counter() - started < 15  # two addresses at most, 2 s each, plus slack
    assert "secret" not in response.text
