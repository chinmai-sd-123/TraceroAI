"""Lightweight tests for the SDK's ergonomic tracing (context manager + decorator).

Run from sdks/python:  python -m pytest test_sdk_ergonomics.py
No live API needed — TraceroClient.log_trace is stubbed to capture the payload.
"""

from uuid import uuid4

from traceroai import TraceroClient


def _client_capturing(captured: list[dict]) -> TraceroClient:
    client = TraceroClient(base_url="http://test")

    def fake_log_trace(**payload):
        captured.append(payload)
        return uuid4()

    client.log_trace = fake_log_trace  # type: ignore[method-assign]
    return client


def test_context_manager_builds_and_sends_trace() -> None:
    captured: list[dict] = []
    client = _client_capturing(captured)

    with client.trace("How long is a refund?") as t:
        t.log_retrieval([{"rank": 1, "chunk_id": "c1", "text": "5 to 7 days"}], strategy="lexical")
        t.log_generation("5 to 7 business days", model="gpt-4o-mini")

    assert t.trace_id is not None
    assert len(captured) == 1
    payload = captured[0]
    assert payload["query"]["original"] == "How long is a refund?"
    assert payload["retrieval"]["strategy"] == "lexical"
    assert payload["generation"]["answered"] is True
    assert payload["generation"]["model"] == "gpt-4o-mini"
    assert "total_ms" in payload["latency"]


def test_exception_marks_trace_unanswered_and_still_sends() -> None:
    captured: list[dict] = []
    client = _client_capturing(captured)

    try:
        with client.trace("boom") as t:
            t.log_generation("partial", model="gpt-4o-mini")
            raise ValueError("pipeline failed")
    except ValueError:
        pass

    # Trace still sent (for debugging the failure), marked unanswered.
    assert len(captured) == 1
    assert captured[0]["generation"]["answered"] is False


def test_decorator_traces_and_returns_answer() -> None:
    captured: list[dict] = []
    client = _client_capturing(captured)

    @client.traced(model="gpt-4o-mini", strategy="lexical_top_k")
    def answer(query: str):
        return "an answer", [{"rank": 1, "chunk_id": "c1", "text": "ctx"}]

    result = answer("a question")

    assert result == "an answer"  # caller gets the answer transparently
    assert len(captured) == 1
    assert captured[0]["query"]["original"] == "a question"
    assert captured[0]["retrieval"]["strategy"] == "lexical_top_k"
