"""Issues: failing traces grouped by label and top source, with resolve and regression."""

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.routes.traces as traces_route
from app.core.config import get_settings
from app.db import models
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)


@pytest.fixture
def project() -> str:
    return f"issues-{uuid4().hex[:8]}"


def _trace(project: str, question: str, *, source: str | None, label: str, headers: dict | None = None) -> str:
    chunk = {"rank": 1, "chunk_id": "c1", "text": "Refunds take 5 to 7 business days."}
    if source:
        chunk["document_id"] = source
    trace_id = client.post(
        "/v1/traces",
        headers=headers or {},
        json={
            "project": {"project_id": project},
            "query": {"original": question},
            "retrieval": {"chunks": [chunk]},
            "generation": {"model": "m", "answer": "Refunds take 5 to 7 business days."},
        },
    ).json()["trace_id"]
    _relabel(trace_id, label)
    return trace_id


def _relabel(trace_id: str, label: str) -> None:
    # Stands in for the judge's verdict replacing the estimate.
    with SessionLocal() as db:
        db.execute(text("UPDATE traces SET diagnosis_label = :l WHERE trace_id = :t"), {"l": label, "t": trace_id})
        db.commit()


def _issues(project: str, **params) -> list[dict]:
    response = client.get("/v1/issues", params={"project_id": project, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_migration_and_model_compute_the_same_key() -> None:
    migration = Path(__file__).parents[1] / "migrations" / "versions" / "0006_issues.py"
    match = re.search(r"ISSUE_KEY = \((.*?)\n\)", migration.read_text(encoding="utf-8"), re.S)
    assert match is not None
    scope: dict = {}
    exec("ISSUE_KEY = (" + match.group(1) + "\n)", scope)
    assert scope["ISSUE_KEY"] == models.ISSUE_KEY_SQL


def test_failures_group_by_label_and_top_source(project) -> None:
    _trace(project, "How long is a refund?", source="refunds.md", label="retrieval_miss")
    _trace(project, "Refund timing?", source="refunds.md", label="retrieval_miss")
    newest = _trace(project, "Refund timing?", source="refunds.md", label="retrieval_miss")
    _trace(project, "Where is my parcel?", source="shipping.md", label="retrieval_miss")
    _trace(project, "Who are you?", source=None, label="wrong_answer")
    _trace(project, "Fine question", source="refunds.md", label="healthy_answer")

    issues = {i["issue_key"]: i for i in _issues(project)}
    assert set(issues) == {"retrieval_miss|refunds.md", "retrieval_miss|shipping.md", "wrong_answer|(no context)"}

    refunds = issues["retrieval_miss|refunds.md"]
    assert (refunds["label"], refunds["source"], refunds["status"]) == ("retrieval_miss", "refunds.md", "open")
    assert (refunds["count"], refunds["questions"]) == (3, 2)
    assert refunds["recent_questions"] == ["Refund timing?", "How long is a refund?"]
    assert refunds["latest_trace_id"] == newest
    # Traces in an issue can be listed directly.
    members = client.get("/v1/traces", params={"project_id": project, "issue_key": "retrieval_miss|refunds.md"}).json()
    assert len(members) == 3


def test_a_changed_diagnosis_moves_the_trace(project) -> None:
    first = _trace(project, "q1", source="refunds.md", label="unsupported_claim")
    _trace(project, "q2", source="refunds.md", label="unsupported_claim")
    _relabel(first, "healthy_answer")  # the judge disagreed with the estimate
    (issue,) = _issues(project)
    assert issue["count"] == 1


def test_resolve_then_new_failure_regresses_then_reopen(project) -> None:
    _trace(project, "q", source="refunds.md", label="wrong_answer")
    ref = {"project_id": project, "issue_key": "wrong_answer|refunds.md"}

    assert client.post("/v1/issues/resolve", json=ref).status_code == 200
    (issue,) = _issues(project)
    assert issue["status"] == "resolved" and issue["count_since_resolved"] == 0
    assert _issues(project, status="open") == []

    _trace(project, "q again", source="refunds.md", label="wrong_answer")
    (issue,) = _issues(project)
    assert issue["status"] == "regressed" and issue["count_since_resolved"] == 1

    assert client.post("/v1/issues/reopen", json=ref).status_code == 200
    (issue,) = _issues(project)
    assert issue["status"] == "open" and issue["resolved_at"] is None


def test_regressed_issues_are_listed_first(project) -> None:
    _trace(project, "a", source="a.md", label="wrong_answer")
    _trace(project, "b", source="b.md", label="wrong_answer")
    client.post("/v1/issues/resolve", json={"project_id": project, "issue_key": "wrong_answer|a.md"})
    _trace(project, "a again", source="a.md", label="wrong_answer")
    assert [i["status"] for i in _issues(project)] == ["regressed", "open"]


def test_unknown_issue_is_not_found(project) -> None:
    response = client.post("/v1/issues/resolve", json={"project_id": project, "issue_key": "wrong_answer|nope"})
    assert response.status_code == 404


def test_a_project_key_cannot_touch_another_projects_issue(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "project_api_keys", {"key_acme": "acme-issues", "key_globex": "globex-issues"})
    monkeypatch.setattr(settings, "admin_api_keys", [])
    acme = {"Authorization": "Bearer key_acme"}
    globex = {"Authorization": "Bearer key_globex"}
    _trace("acme-issues", "q", source="x.md", label="wrong_answer", headers=acme)
    ref = {"project_id": "acme-issues", "issue_key": "wrong_answer|x.md"}

    assert client.post("/v1/issues/resolve", json=ref, headers=globex).status_code == 404
    assert client.get("/v1/issues", params={"project_id": "acme-issues"}, headers=globex).json() == []
    assert client.post("/v1/issues/resolve", json=ref, headers=acme).status_code == 200

    with SessionLocal() as db:
        db.execute(text("DELETE FROM issue_states WHERE project_id = 'acme-issues'"))
        db.commit()
