"""Limits on the endpoints anyone can call: playground, rate limits, feedback."""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import get_settings
from app.main import app
from app.services.rate_limiter import check_rate_limit, client_ip

client = TestClient(app)


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


# --- playground ---


def test_playground_is_off_by_default() -> None:
    response = client.post("/v1/playground", json={"question": "How long does a refund take?"})
    assert response.status_code == 404


class TestEnabledPlayground:
    @pytest.fixture(autouse=True)
    def _enable(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "playground_enabled", True)

    def test_answers_a_question(self) -> None:
        response = client.post("/v1/playground", json={"question": "How long does a refund take?"})
        assert response.status_code == 200
        assert response.json()["judged_by"] == "deterministic"  # no judge configured in tests

    def test_rejects_long_or_empty_questions(self) -> None:
        assert client.post("/v1/playground", json={"question": "x" * 501}).status_code == 422
        assert client.post("/v1/playground", json={"question": ""}).status_code == 422

    def test_spoofed_forwarded_for_does_not_reset_the_limit(self) -> None:
        # Without a trusted proxy, X-Forwarded-For is ignored: every request
        # below comes from the same socket address and shares one limit.
        statuses = [
            client.post(
                "/v1/playground",
                json={"question": "How long does a refund take?"},
                headers={"X-Forwarded-For": f"203.0.113.{i}"},
            ).status_code
            for i in range(11)
        ]
        assert statuses[:10] == [200] * 10
        assert statuses[10] == 429


# --- rate limiting without Redis ---


def test_limit_holds_without_redis() -> None:
    results = [check_rate_limit("t", "a", limit=3, window_seconds=60) for _ in range(4)]
    assert results == [True, True, True, False]
    # Separate identities and buckets are counted separately.
    assert check_rate_limit("t", "b", limit=3, window_seconds=60) is True
    assert check_rate_limit("other", "a", limit=3, window_seconds=60) is True


def test_limit_holds_when_redis_is_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "redis_url", "redis://127.0.0.1:1/0")
    results = [check_rate_limit("down", "a", limit=2, window_seconds=60) for _ in range(3)]
    assert results == [True, True, False]


def test_window_resets(monkeypatch) -> None:
    from app.services import rate_limiter

    now = [1000.0]
    monkeypatch.setattr(rate_limiter.time, "monotonic", lambda: now[0])
    assert check_rate_limit("w", "a", limit=1, window_seconds=60) is True
    assert check_rate_limit("w", "a", limit=1, window_seconds=60) is False
    now[0] += 61
    assert check_rate_limit("w", "a", limit=1, window_seconds=60) is True


# --- client address ---


@pytest.mark.parametrize(
    ("proxies", "forwarded", "expected"),
    [
        (0, "198.51.100.7", "10.0.0.9"),  # no trusted proxy: header ignored
        (1, "198.51.100.7", "198.51.100.7"),  # one proxy appended the real address
        (1, "6.6.6.6, 198.51.100.7", "198.51.100.7"),  # client-sent entry is ignored
        (2, "6.6.6.6, 198.51.100.7, 10.1.1.1", "198.51.100.7"),
        (2, "198.51.100.7", "10.0.0.9"),  # fewer entries than proxies
        (1, "not-an-ip", "10.0.0.9"),
        (1, None, "10.0.0.9"),
    ],
)
def test_client_ip_trusts_only_known_proxies(monkeypatch, proxies, forwarded, expected) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxy_count", proxies)
    assert client_ip(_request("10.0.0.9", forwarded)) == expected


# --- feedback cap ---


def test_feedback_per_trace_is_capped(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "max_feedback_per_trace", 2)
    trace_id = client.post(
        "/v1/traces",
        json={
            "query": {"original": "q"},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "t"}]},
            "generation": {"model": "m", "answer": "a"},
        },
    ).json()["trace_id"]

    statuses = [
        client.post(f"/v1/traces/{trace_id}/feedback", json={"rating": "thumbs_up"}).status_code
        for _ in range(3)
    ]

    assert statuses == [201, 201, 409]
    assert len(client.get(f"/v1/traces/{trace_id}").json()["feedback"]) == 2


def test_feedback_on_a_missing_trace_is_404() -> None:
    response = client.post(
        "/v1/traces/3fa85f64-5717-4562-b3fc-2c963f66afa6/feedback", json={"rating": "thumbs_up"}
    )
    assert response.status_code == 404
