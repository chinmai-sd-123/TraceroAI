"""Deleting traces, and the retention purge."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.routes.traces as traces_route
from app import retention
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.services.trace_repository import TraceRepository
from app.worker import DeepEvalWorker
from tests.test_deep_groundedness import make_trace_payload

client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)
    settings = get_settings()
    monkeypatch.setattr(settings, "project_api_keys", {"key_a": "ret-a", "key_b": "ret-b"})
    monkeypatch.setattr(settings, "admin_api_keys", ["key_admin"])


def _ingest(key: str | None = None) -> str:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return client.post("/v1/traces", json=make_trace_payload(), headers=headers).json()["trace_id"]


def _age(trace_id: str, days: int) -> None:
    with SessionLocal() as db:
        db.execute(
            text("UPDATE traces SET created_at = now() - make_interval(days => :d) "
                 "WHERE trace_id = CAST(:id AS uuid)"),
            {"d": days, "id": trace_id},
        )
        db.commit()


def _exists(trace_id: str) -> bool:
    response = client.get(f"/v1/traces/{trace_id}", headers={"Authorization": "Bearer key_admin"})
    return response.status_code == 200


# --- DELETE /v1/traces/{id} ---


def test_a_project_key_deletes_its_own_trace() -> None:
    trace_id = _ingest("key_a")
    response = client.delete(f"/v1/traces/{trace_id}", headers={"Authorization": "Bearer key_a"})
    assert response.status_code == 204
    assert not _exists(trace_id)


def test_a_project_key_cannot_delete_another_projects_trace() -> None:
    trace_id = _ingest("key_b")
    response = client.delete(f"/v1/traces/{trace_id}", headers={"Authorization": "Bearer key_a"})
    assert response.status_code == 404  # not 403: don't confirm it exists
    assert _exists(trace_id)


def test_an_admin_key_deletes_any_trace() -> None:
    trace_id = _ingest("key_b")
    response = client.delete(
        f"/v1/traces/{trace_id}", headers={"Authorization": "Bearer key_admin"}
    )
    assert response.status_code == 204


def test_deleting_without_a_key_is_refused_when_keys_are_required(monkeypatch) -> None:
    trace_id = _ingest("key_a")
    monkeypatch.setattr(get_settings(), "require_api_key", True)
    assert client.delete(f"/v1/traces/{trace_id}").status_code == 401
    assert _exists(trace_id)


def test_deleting_a_missing_trace_is_404() -> None:
    response = client.delete(
        f"/v1/traces/{uuid4()}", headers={"Authorization": "Bearer key_admin"}
    )
    assert response.status_code == 404


# --- retention ---


def test_purge_removes_only_traces_past_the_window() -> None:
    old, recent = _ingest(), _ingest()
    _age(old, 40)
    _age(recent, 10)

    with SessionLocal() as db:
        deleted = TraceRepository(db).purge_older_than(30)

    assert deleted >= 1
    assert not _exists(old)
    assert _exists(recent)


def test_purge_works_in_batches() -> None:
    ids = [_ingest() for _ in range(5)]
    for trace_id in ids:
        _age(trace_id, 400)

    with SessionLocal() as db:
        deleted = TraceRepository(db).purge_older_than(365, batch_size=2)

    assert deleted >= 5
    assert not any(_exists(t) for t in ids)


def test_cli_uses_the_setting_or_a_flag(monkeypatch, capsys) -> None:
    trace_id = _ingest()
    _age(trace_id, 100)

    monkeypatch.setattr(get_settings(), "trace_retention_days", None)
    assert retention.main([]) == 1  # nothing configured: refuses to guess
    assert _exists(trace_id)

    assert retention.main(["--days", "90"]) == 0
    assert "Deleted" in capsys.readouterr().out
    assert not _exists(trace_id)


def test_the_worker_purges_when_retention_is_set(monkeypatch) -> None:
    trace_id = _ingest()
    _age(trace_id, 100)
    worker = DeepEvalWorker(client=None, consumer="test")  # purge doesn't use Redis

    monkeypatch.setattr(get_settings(), "trace_retention_days", None)
    assert worker.purge_expired() == 0
    assert _exists(trace_id)

    monkeypatch.setattr(get_settings(), "trace_retention_days", 90)
    assert worker.purge_expired() >= 1
    assert not _exists(trace_id)
