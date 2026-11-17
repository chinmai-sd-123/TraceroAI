"""Alerts: new issues, regressions and the failure rate reach a webhook once each."""

import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.api.routes.traces as traces_route
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.services import alerts

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_alerts(monkeypatch):
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)
    # As if alerts were being turned on now: everything already stored is known.
    with SessionLocal() as db:
        db.execute(text("DELETE FROM alert_states"))
        db.commit()


@pytest.fixture
def project() -> str:
    return f"alerts-{uuid4().hex[:8]}"


class Webhook:
    """Keeps what it's sent; answers with the given status codes in turn, then 200."""

    def __init__(self, *statuses: int) -> None:
        self.statuses = list(statuses)
        self.received: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        status = self.statuses.pop(0) if self.statuses else 200
        if status < 300:
            self.received.append(json.loads(request.content))
        return httpx.Response(status)

    def about(self, project: str) -> list[dict]:
        return [m for m in self.received if m["event"]["project_id"] == project]


def _settings(**overrides):
    values = {"alert_webhook_url": "http://hooks.test/alerts", "dashboard_url": "http://localhost:3000"}
    return get_settings().model_copy(update={**values, **overrides})


def _check(webhook: Webhook, **overrides) -> int:
    with SessionLocal() as db, httpx.Client(transport=httpx.MockTransport(webhook)) as http:
        return alerts.check(db, _settings(**overrides), http=http)


def _trace(project: str, label: str, *, question: str = "How long do refunds take?", prompt: str = "v1") -> None:
    body = {
        "project": {"project_id": project},
        "query": {"original": question},
        "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c1", "document_id": "refunds.md", "text": "Refunds take 5 days."}]},
        "prompt": {"content": "Answer from the context.", "version": prompt},
        "generation": {"model": "m", "answer": "Refunds take 5 days."},
    }
    trace_id = client.post("/v1/traces", json=body).json()["trace_id"]
    with SessionLocal() as db:  # stands in for the judge's verdict
        db.execute(text("UPDATE traces SET diagnosis_label = :l WHERE trace_id = :t"), {"l": label, "t": trace_id})
        db.commit()


def test_nothing_is_checked_without_a_webhook(project) -> None:
    _check(Webhook())
    _trace(project, "unsupported_claim")
    with SessionLocal() as db:
        assert alerts.check(db, _settings(alert_webhook_url=None)) == 0


def test_a_new_issue_is_announced_once(project) -> None:
    webhook = Webhook()
    _check(webhook)
    _trace(project, "unsupported_claim", question="Can I get a refund after   30 days?")
    _check(webhook)
    _trace(project, "unsupported_claim")
    _check(webhook)

    sent = webhook.about(project)
    assert len(sent) == 1
    assert sent[0]["event"] == {
        "kind": "new_issue",
        "project_id": project,
        "label": "unsupported_claim",
        "grouped_by": "prompt_version",
        "source": "v1",
        "count": 1,
    }
    assert sent[0]["text"] == (
        f"New issue in {project}: Unsupported claim, prompt version v1. "
        "1 failing run so far, latest: “Can I get a refund after 30 days?”\n"
        f"http://localhost:3000/dashboard/issues?project={project}"
    )


def test_issues_from_before_alerts_were_turned_on_are_not_announced(project) -> None:
    _trace(project, "unsupported_claim")
    with SessionLocal() as db:
        db.execute(text("DELETE FROM alert_states"))
        db.commit()
    webhook = Webhook()
    _check(webhook)
    _trace(project, "unsupported_claim")  # the same, older issue
    _check(webhook)
    assert webhook.about(project) == []

    _trace(project, "wrong_answer")  # a new one
    _check(webhook)
    assert [m["event"]["label"] for m in webhook.about(project)] == ["wrong_answer"]


def test_a_regression_is_announced_once_per_resolution(project) -> None:
    webhook = Webhook()
    _check(webhook)
    _trace(project, "unsupported_claim")
    _check(webhook)
    ref = {"project_id": project, "issue_key": "unsupported_claim|v1"}
    assert client.post("/v1/issues/resolve", json=ref).status_code == 200

    _trace(project, "unsupported_claim")
    _trace(project, "unsupported_claim")
    _check(webhook)
    _check(webhook)
    regressions = [m for m in webhook.about(project) if m["event"]["kind"] == "regressed_issue"]
    assert len(regressions) == 1
    assert regressions[0]["event"]["count_since_resolved"] == 2
    assert "failed again after it was marked resolved (2 failing runs since)" in regressions[0]["text"]

    # Resolved again, failing again: a second alert.
    assert client.post("/v1/issues/resolve", json=ref).status_code == 200
    _trace(project, "unsupported_claim")
    _check(webhook)
    assert len([m for m in webhook.about(project) if m["event"]["kind"] == "regressed_issue"]) == 2


def test_the_failure_rate_alerts_when_it_crosses_and_when_it_recovers(project) -> None:
    webhook = Webhook()
    limits = {"alert_failure_rate": 0.5, "alert_min_runs": 4}
    _check(webhook, **limits)
    for label in ("retrieval_miss", "retrieval_miss", "retrieval_miss"):
        _trace(project, label)
    _check(webhook, **limits)
    assert not [m for m in webhook.about(project) if m["event"]["kind"] == "failure_rate"]  # 3 runs: too few

    _trace(project, "healthy_answer")
    _trace(project, "not_diagnosed")  # an agent run counts neither way
    _check(webhook, **limits)
    _check(webhook, **limits)
    rates = [m for m in webhook.about(project) if m["event"]["kind"].startswith("failure_rate")]
    assert [m["event"]["kind"] for m in rates] == ["failure_rate"]
    assert rates[0]["event"] == {
        "kind": "failure_rate",
        "project_id": project,
        "failure_rate": 0.75,
        "runs": 4,
        "failing": 3,
        "window_minutes": 60,
    }
    assert rates[0]["text"].startswith(f"{project}: 75% of answers failed in the last hour (3 of 4 diagnosed runs")

    for _ in range(3):
        _trace(project, "healthy_answer")
    _check(webhook, **limits)
    _check(webhook, **limits)
    rates = [m for m in webhook.about(project) if m["event"]["kind"].startswith("failure_rate")]
    assert [m["event"]["kind"] for m in rates] == ["failure_rate", "failure_rate_recovered"]
    assert rates[1]["text"].startswith(f"{project} recovered: 43% of answers failed")


def test_an_alert_the_webhook_refuses_is_sent_again_next_check(project) -> None:
    webhook = Webhook()
    _check(webhook)
    _trace(project, "wrong_answer")
    webhook.statuses = [500] * 50  # down: every alert due this check fails
    _check(webhook)
    assert webhook.about(project) == []

    webhook.statuses = []
    _check(webhook)
    assert [m["event"]["kind"] for m in webhook.about(project)] == ["new_issue"]
