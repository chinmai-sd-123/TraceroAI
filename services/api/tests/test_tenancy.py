import pytest
from fastapi.testclient import TestClient

from app.api.routes import traces as traces_route
from app.core.config import get_settings
from app.core.tenancy import api_key_required
from app.main import app

client = TestClient(app)


def _eval_run_payload() -> dict:
    return {
        "run_type": "regression",
        "dataset": {"dataset_id": "tenancy-set", "name": "Tenancy set"},
        "pipeline": {"pipeline_version": "tenancy-v1"},
        "summary": {"total_cases": 1, "passed_cases": 1, "failed_cases": 0, "pass_rate": 1.0},
        "cases": [{"case_id": "c1", "question": "q", "passed": True}],
    }


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


def test_no_key_falls_back_to_client_project() -> None:
    # No key (allowed while keys are optional) -> the client-provided project is kept.
    trace_id = _ingest(None)

    project = client.get(f"/v1/traces/{trace_id}").json()["project"]["project_id"]
    assert project == "demo-rag"  # ProjectInfo default


def test_list_filters_by_project() -> None:
    acme_id = _ingest("key_acme")
    globex_id = _ingest("key_globex")

    acme_ids = {t["trace_id"] for t in client.get("/v1/traces?project_id=acme").json()}
    assert acme_id in acme_ids
    assert globex_id not in acme_ids


def test_unknown_key_is_rejected_even_when_keys_are_optional() -> None:
    # A sent-but-wrong key is a misconfigured client, not an anonymous one —
    # accepting it would file the trace under whatever project the client claims.
    response = client.post(
        "/v1/traces", json=_payload(), headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("app_env", "explicit", "expected"),
    [
        ("development", None, False),
        ("testing", None, False),
        ("staging", None, True),
        ("production", None, True),
        ("production", False, False),  # explicit setting always wins
        ("development", True, True),
    ],
)
def test_api_key_required_defaults_to_on_outside_development(
    monkeypatch, app_env: str, explicit: bool | None, expected: bool
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "app_env", app_env)
    monkeypatch.setattr(settings, "require_api_key", explicit)
    assert api_key_required() is expected


def test_eval_run_is_stamped_with_the_key_project() -> None:
    payload = _eval_run_payload()
    payload["project"] = {"project_id": "claimed-by-client"}
    response = client.post(
        "/v1/eval-runs", json=payload, headers={"Authorization": "Bearer key_acme"}
    )
    assert response.status_code == 201

    run_id = response.json()["eval_run_id"]
    assert client.get(f"/v1/eval-runs/{run_id}").json()["project"]["project_id"] == "acme"


def test_feedback_with_a_key_cannot_touch_another_projects_trace() -> None:
    globex_trace = _ingest("key_globex")
    response = client.post(
        f"/v1/traces/{globex_trace}/feedback",
        json={"rating": "thumbs_up"},
        headers={"Authorization": "Bearer key_acme"},
    )
    assert response.status_code == 404  # not 403: don't confirm the trace exists


def test_feedback_ignores_a_client_supplied_timestamp() -> None:
    trace_id = _ingest(None)
    response = client.post(
        f"/v1/traces/{trace_id}/feedback",
        json={"rating": "thumbs_up", "created_at": "2000-01-01T00:00:00Z"},
    )
    assert response.status_code == 201
    assert not response.json()["created_at"].startswith("2000-")


def test_anonymous_feedback_is_rate_limited(monkeypatch) -> None:
    trace_id = _ingest(None)
    monkeypatch.setattr(traces_route, "check_rate_limit", lambda **_: False)

    anonymous = client.post(f"/v1/traces/{trace_id}/feedback", json={"rating": "thumbs_up"})
    assert anonymous.status_code == 429


def test_feedback_comment_length_is_capped() -> None:
    trace_id = _ingest(None)
    response = client.post(
        f"/v1/traces/{trace_id}/feedback",
        json={"rating": "thumbs_down", "comment": "x" * 2001},
    )
    assert response.status_code == 422


class TestApiKeyEnforcement:
    @pytest.fixture(autouse=True)
    def _enforce(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "require_api_key", True)

    def test_grading_requires_a_key(self) -> None:
        body = {"question": "q", "expected": "a", "actual": "a"}
        assert client.post("/v1/eval/grade", json=body).status_code == 401
        # With a key it gets past auth; tests run without a judge, hence 503.
        authed = client.post(
            "/v1/eval/grade", json=body, headers={"Authorization": "Bearer key_acme"}
        )
        assert authed.status_code == 503

    def test_sync_deep_eval_requires_a_key(self) -> None:
        response = client.post("/v1/traces?sync_deep_eval=true", json=_payload())
        assert response.status_code == 401

    def test_eval_run_ingest_requires_a_key(self) -> None:
        assert client.post("/v1/eval-runs", json=_eval_run_payload()).status_code == 401

    def test_anonymous_feedback_still_allowed(self) -> None:
        # The public dashboard's widget has no key; feedback stays open (rate-limited).
        trace_id = client.post(
            "/v1/traces", json=_payload(), headers={"Authorization": "Bearer key_acme"}
        ).json()["trace_id"]
        response = client.post(f"/v1/traces/{trace_id}/feedback", json={"rating": "thumbs_up"})
        assert response.status_code == 201

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
