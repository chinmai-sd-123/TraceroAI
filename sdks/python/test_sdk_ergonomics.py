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


def test_failed_generation_still_sends_a_valid_trace() -> None:
    # When generation never ran (e.g. LLM quota error), the trace must still be
    # sent with a non-empty placeholder answer that captures the failure.
    captured: list[dict] = []
    client = _client_capturing(captured)

    try:
        with client.trace("boom") as t:
            raise RuntimeError("429 quota exceeded")
    except RuntimeError:
        pass

    assert len(captured) == 1
    answer = captured[0]["generation"]["answer"]
    assert answer  # non-empty -> passes the schema's min_length
    assert "429 quota exceeded" in answer


def test_send_failure_is_best_effort_and_does_not_raise() -> None:
    # A failure to SEND the trace must never break the caller's code.
    import pytest

    client = TraceroClient(base_url="http://test")

    def boom_log_trace(**payload):
        raise ConnectionError("API unreachable")

    client.log_trace = boom_log_trace  # type: ignore[method-assign]

    with pytest.warns(UserWarning, match="failed to send trace"):
        with client.trace("q") as t:
            t.log_generation("an answer", model="gpt-4o-mini")

    assert t.trace_id is None  # send failed, but no exception propagated


def test_send_failure_does_not_mask_callers_exception() -> None:
    # If the caller's code raises AND sending fails, the caller's exception wins.
    import pytest

    client = TraceroClient(base_url="http://test")

    def boom_log_trace(**payload):
        raise ConnectionError("API unreachable")

    client.log_trace = boom_log_trace  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="user bug"):
        with client.trace("q"):
            raise ValueError("user bug")


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
