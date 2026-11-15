"""API keys stored in the database, the key CLI, and per-key rate limits."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api.routes.traces as traces_route
from app import keys as keys_cli
from app.core.config import get_settings
from app.db.models import ApiKeyRecord
from app.db.session import SessionLocal
from app.main import app
from app.services import api_keys
from tests.test_deep_groundedness import make_trace_payload

client = TestClient(app)


@pytest.fixture(autouse=True)
def _keys_required(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_api_key", True)
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


@pytest.fixture
def project() -> str:
    return f"keys-{uuid4().hex[:8]}"


def _create(**kwargs) -> tuple[str, ApiKeyRecord]:
    with SessionLocal() as db:
        return api_keys.create_key(db, name="test", **kwargs)


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def test_a_project_key_writes_to_and_reads_only_its_project(project) -> None:
    key, _ = _create(project_id=project)

    trace_id = client.post("/v1/traces", json=make_trace_payload(), headers=_auth(key)).json()[
        "trace_id"
    ]

    assert client.get(f"/v1/traces/{trace_id}", headers=_auth(key)).json()["project"][
        "project_id"
    ] == project
    assert client.get("/v1/traces/projects", headers=_auth(key)).json() == [project]


def test_an_admin_key_reads_every_project(project) -> None:
    project_key, _ = _create(project_id=project)
    admin_key, _ = _create(admin=True)
    client.post("/v1/traces", json=make_trace_payload(), headers=_auth(project_key))

    assert project in client.get("/v1/traces/projects", headers=_auth(admin_key)).json()


def test_only_the_hash_is_stored(project) -> None:
    key, record = _create(project_id=project)

    with SessionLocal() as db:
        stored = db.scalar(select(ApiKeyRecord).where(ApiKeyRecord.key_id == record.key_id))
    assert key.startswith("trk_") and len(key) > 40
    assert stored.key_hash == api_keys.hash_key(key) != key
    assert stored.prefix == key[:12]
    assert key not in {stored.key_hash, stored.prefix, stored.name}


def test_a_revoked_key_is_rejected_at_once(project) -> None:
    key, record = _create(project_id=project)
    assert client.get("/v1/traces", headers=_auth(key)).status_code == 200

    with SessionLocal() as db:
        api_keys.revoke(db, record.prefix)

    assert client.get("/v1/traces", headers=_auth(key)).status_code == 401
    assert client.post("/v1/traces", json=make_trace_payload(), headers=_auth(key)).status_code == 401


def test_last_used_is_recorded(project) -> None:
    key, record = _create(project_id=project)
    client.get("/v1/traces", headers=_auth(key))

    with SessionLocal() as db:
        assert db.get(ApiKeyRecord, record.key_id).last_used_at is not None


def test_environment_keys_still_work(monkeypatch, project) -> None:
    monkeypatch.setattr(get_settings(), "project_api_keys", {"env_key": project})
    response = client.post("/v1/traces", json=make_trace_payload(), headers=_auth("env_key"))
    assert response.status_code == 202


def test_a_key_needs_exactly_one_scope() -> None:
    with SessionLocal() as db, pytest.raises(ValueError):
        api_keys.create_key(db, name="x")
    with SessionLocal() as db, pytest.raises(ValueError):
        api_keys.create_key(db, name="x", project_id="p", admin=True)


def test_cli_create_list_revoke(capsys, project) -> None:
    assert keys_cli.main(["create", "--project", project, "--name", "cli test"]) == 0
    created = capsys.readouterr().out
    key = next(word for word in created.split() if word.startswith("trk_"))
    assert client.get("/v1/traces", headers=_auth(key)).status_code == 200

    assert keys_cli.main(["list"]) == 0
    listing = capsys.readouterr().out
    assert key[:12] in listing and key not in listing  # the prefix, never the key

    assert keys_cli.main(["revoke", key[:12]]) == 0
    assert client.get("/v1/traces", headers=_auth(key)).status_code == 401
    assert keys_cli.main(["revoke", key[:12]]) == 1  # nothing active left to revoke


def test_ingest_is_rate_limited_per_key(monkeypatch, project) -> None:
    monkeypatch.setattr(get_settings(), "ingest_rate_limit_per_minute", 2)
    first, _ = _create(project_id=project)
    second, _ = _create(project_id=project)

    statuses = [
        client.post("/v1/traces", json=make_trace_payload(), headers=_auth(first)).status_code
        for _ in range(3)
    ]
    other = client.post("/v1/traces", json=make_trace_payload(), headers=_auth(second))

    assert statuses == [202, 202, 429]
    assert other.status_code == 202  # a separate key has its own allowance


def test_grading_is_rate_limited_per_key(monkeypatch, project) -> None:
    monkeypatch.setattr(get_settings(), "grade_rate_limit_per_minute", 1)
    key, _ = _create(project_id=project)
    body = {"question": "q", "expected": "a", "actual": "a"}

    first = client.post("/v1/eval/grade", json=body, headers=_auth(key))
    second = client.post("/v1/eval/grade", json=body, headers=_auth(key))

    assert first.status_code == 503  # past the limit check; no judge in tests
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "60"
