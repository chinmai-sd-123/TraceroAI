import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _project_keys(monkeypatch):
    # A two-tenant key map for these tests (overrides .env).
    settings = get_settings()
    monkeypatch.setattr(
        settings, "project_api_keys", {"key_acme": "acme", "key_globex": "globex"}
    )


def _payload() -> dict:
    return {
        "query": {"original": "tenancy test question"},
        "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c1", "text": "context text"}]},
        "generation": {"model": "gpt-4o-mini", "answer": "an answer"},
    }


def _ingest(api_key: str | None) -> str:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return client.post("/v1/traces", json=_payload(), headers=headers).json()["trace_id"]


def test_api_key_stamps_project_on_trace() -> None:
    trace_id = _ingest("key_acme")

    project = client.get(f"/v1/traces/{trace_id}").json()["project"]["project_id"]
    assert project == "acme"


def test_unknown_key_falls_back_to_client_project() -> None:
    # No / unknown key -> the client-provided default project is kept.
    trace_id = _ingest(None)

    project = client.get(f"/v1/traces/{trace_id}").json()["project"]["project_id"]
    assert project == "demo-rag"  # ProjectInfo default


def test_list_filters_by_project() -> None:
    acme_id = _ingest("key_acme")
    globex_id = _ingest("key_globex")

    acme_ids = {t["trace_id"] for t in client.get("/v1/traces?project_id=acme").json()}
    assert acme_id in acme_ids
    assert globex_id not in acme_ids


class TestApiKeyEnforcement:
    @pytest.fixture(autouse=True)
    def _enforce(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "require_api_key", True)

    def test_valid_key_is_accepted(self) -> None:
        response = client.post(
            "/v1/traces", json=_payload(), headers={"Authorization": "Bearer key_acme"}
        )
        assert response.status_code == 202

    def test_missing_key_is_rejected(self) -> None:
        response = client.post("/v1/traces", json=_payload())
        assert response.status_code == 401

    def test_unknown_key_is_rejected(self) -> None:
        response = client.post(
            "/v1/traces", json=_payload(), headers={"Authorization": "Bearer nope"}
        )
        assert response.status_code == 401

    def test_reads_stay_open_without_a_key(self) -> None:
        # Recruiters/visitors must be able to browse the dashboard data unauthenticated.
        assert client.get("/v1/traces").status_code == 200
        assert client.get("/v1/jobs/stats").status_code == 200
