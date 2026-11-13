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
    monkeypatch.setattr(settings, "admin_api_keys", ["key_admin"])
    monkeypatch.setattr(settings, "public_read_projects", [])


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

    def test_anonymous_feedback_is_rejected(self) -> None:
        # The dashboard sends feedback from its server with its own key, so
        # nothing legitimate posts feedback without one.
        trace_id = client.post(
            "/v1/traces", json=_payload(), headers={"Authorization": "Bearer key_acme"}
        ).json()["trace_id"]
        response = client.post(f"/v1/traces/{trace_id}/feedback", json={"rating": "thumbs_up"})
        assert response.status_code == 401

    def test_admin_key_adds_feedback_to_any_project_without_rate_limit(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(traces_route, "check_rate_limit", lambda **_: False)
        trace_id = client.post(
            "/v1/traces", json=_payload(), headers={"Authorization": "Bearer key_globex"}
        ).json()["trace_id"]
        response = client.post(
            f"/v1/traces/{trace_id}/feedback",
            json={"rating": "thumbs_up"},
            headers={"Authorization": "Bearer key_admin"},
        )
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

    @pytest.mark.parametrize(
        "path",
        [
            "/v1/traces",
            "/v1/traces/projects",
            "/v1/traces/3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "/v1/eval-runs",
            "/v1/eval-runs/projects",
            "/v1/eval-runs/3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "/v1/jobs/stats",
        ],
    )
    def test_reads_without_a_key_are_rejected(self, path: str) -> None:
        assert client.get(path).status_code == 401

    def test_unknown_key_is_rejected_on_reads(self) -> None:
        response = client.get("/v1/traces", headers={"Authorization": "Bearer nope"})
        assert response.status_code == 401

    def test_public_projects_are_readable_without_a_key(self, monkeypatch) -> None:
        monkeypatch.setattr(get_settings(), "public_read_projects", ["globex"])
        acme_id = _ingest("key_acme")
        globex_id = _ingest("key_globex")

        visible = {t["trace_id"] for t in client.get("/v1/traces").json()}
        assert globex_id in visible
        assert acme_id not in visible
        assert client.get(f"/v1/traces/{acme_id}").status_code == 404
        assert client.get("/v1/traces/projects").json() == ["globex"]


def _get(path: str, key: str) -> list | dict:
    response = client.get(path, headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200, response.text
    return response.json()


class TestReadIsolation:
    """A project key reads only its own project, whatever it asks for."""

    def test_trace_list_is_limited_to_the_keys_project(self) -> None:
        acme_id, globex_id = _ingest("key_acme"), _ingest("key_globex")

        unfiltered = {t["trace_id"] for t in _get("/v1/traces", "key_acme")}
        assert acme_id in unfiltered and globex_id not in unfiltered
        assert {t["project"]["project_id"] for t in _get("/v1/traces", "key_acme")} == {"acme"}

        # Asking for another project's traces returns nothing rather than an error.
        assert _get("/v1/traces?project_id=globex", "key_acme") == []

    def test_another_projects_trace_is_not_found(self) -> None:
        globex_id = _ingest("key_globex")
        response = client.get(
            f"/v1/traces/{globex_id}", headers={"Authorization": "Bearer key_acme"}
        )
        assert response.status_code == 404
        assert _get(f"/v1/traces/{globex_id}", "key_globex")["trace_id"] == globex_id

    def test_project_list_shows_only_the_keys_project(self) -> None:
        _ingest("key_acme")
        _ingest("key_globex")
        assert _get("/v1/traces/projects", "key_acme") == ["acme"]

    def test_eval_runs_are_isolated(self) -> None:
        def post_run(key: str) -> str:
            response = client.post(
                "/v1/eval-runs",
                json=_eval_run_payload(),
                headers={"Authorization": f"Bearer {key}"},
            )
            return response.json()["eval_run_id"]

        acme_run, globex_run = post_run("key_acme"), post_run("key_globex")

        listed = {r["eval_run_id"] for r in _get("/v1/eval-runs", "key_acme")}
        assert acme_run in listed and globex_run not in listed
        assert _get("/v1/eval-runs/projects", "key_acme") == ["acme"]
        assert _get("/v1/eval-runs?project_id=globex", "key_acme") == []
        response = client.get(
            f"/v1/eval-runs/{globex_run}", headers={"Authorization": "Bearer key_acme"}
        )
        assert response.status_code == 404

    def test_admin_key_reads_every_project(self) -> None:
        acme_id, globex_id = _ingest("key_acme"), _ingest("key_globex")

        listed = {t["trace_id"] for t in _get("/v1/traces", "key_admin")}
        assert {acme_id, globex_id} <= listed
        assert {"acme", "globex"} <= set(_get("/v1/traces/projects", "key_admin"))
        assert _get(f"/v1/traces/{globex_id}", "key_admin")["trace_id"] == globex_id
