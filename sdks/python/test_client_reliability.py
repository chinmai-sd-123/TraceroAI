"""The SDK must never break or stall the application it runs in.

Run from sdks/python:  python -m pytest test_client_reliability.py
Uses httpx.MockTransport (no server) and a closed local port (a dead server).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from uuid import UUID, uuid4

import httpx
import pytest

from traceroai import TraceroClient, TraceroError, __version__

DEAD_SERVER = "http://127.0.0.1:9"  # nothing listens on the discard port


def _trace_args() -> dict:
    return {
        "query": {"original": "q"},
        "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c", "text": "t"}]},
        "generation": {"model": "m", "answer": "a"},
    }


class Recorder:
    """A mock server: answers each POST with the next scripted status."""

    def __init__(self, statuses: list[int] | None = None, delay: float = 0.0) -> None:
        self.statuses = list(statuses or [202])
        self.delay = delay
        self.requests: list[httpx.Request] = []
        self.release = threading.Event()
        self.release.set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.release.wait(5)
        time.sleep(self.delay)
        self.requests.append(request)
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        if request.method == "GET":
            return httpx.Response(200, json={"trace_id": request.url.path.rsplit("/", 1)[-1]})
        body = json.loads(request.content)
        return httpx.Response(status, json={"trace_id": body.get("trace_id"), "status": "accepted"})

    def posted_ids(self) -> list[str]:
        return [json.loads(r.content)["trace_id"] for r in self.requests if r.method == "POST"]


def _client(recorder: Recorder, **kwargs) -> TraceroClient:
    kwargs.setdefault("retry_backoff_seconds", 0)
    kwargs.setdefault("flush_on_exit_seconds", 0)
    return TraceroClient(
        base_url="http://tracero.test", transport=httpx.MockTransport(recorder), **kwargs
    )


# --- a dead or slow server never reaches the host ---


@pytest.mark.parametrize("background", [True, False])
def test_dead_server_raises_nothing(background: bool) -> None:
    client = TraceroClient(
        base_url=DEAD_SERVER, background=background, max_retries=0, flush_on_exit_seconds=0
    )

    trace_id = client.log_trace(**_trace_args())
    with client.trace("q") as t:
        t.log_generation("a", model="m")

    @client.traced(model="m")
    def answer(query: str):
        return "a", [{"rank": 1, "chunk_id": "c", "text": "t"}]

    assert answer("q") == "a"
    assert isinstance(trace_id, UUID) and isinstance(t.trace_id, UUID)
    client.flush(5)


def test_background_sending_does_not_wait_for_a_slow_server() -> None:
    recorder = Recorder(delay=0.3)
    client = _client(recorder)

    started = time.perf_counter()
    for _ in range(5):
        with client.trace("q") as t:
            t.log_generation("a", model="m")
    elapsed = time.perf_counter() - started

    assert elapsed < 0.2  # sent inline these would take 1.5 s
    assert client.flush(10)
    assert len(recorder.posted_ids()) == 5


def test_send_failures_are_logged_not_raised(caplog) -> None:
    client = _client(Recorder([500]), background=False, max_retries=1)
    with caplog.at_level("WARNING", logger="traceroai"):
        client.log_trace(**_trace_args())
    assert "was not sent" in caplog.text and "HTTP 500" in caplog.text


def test_raise_on_error_is_opt_in() -> None:
    client = _client(Recorder([422]), background=False, raise_on_error=True)
    with pytest.raises(TraceroError, match="HTTP 422"):
        client.log_trace(**_trace_args())


# --- ids and retries ---


def test_trace_id_is_generated_by_the_client_and_kept_across_retries() -> None:
    recorder = Recorder([503, 502, 202])
    client = _client(recorder, background=False, max_retries=3)

    trace_id = client.log_trace(**_trace_args())

    assert recorder.posted_ids() == [str(trace_id)] * 3


def test_context_manager_id_is_known_before_sending_and_is_the_one_sent() -> None:
    recorder = Recorder()
    client = _client(recorder, background=False)

    with client.trace("q") as t:
        known_inside = t.trace_id
        t.log_generation("a", model="m")

    assert recorder.posted_ids() == [str(known_inside)]


def test_client_errors_are_not_retried() -> None:
    recorder = Recorder([422])
    client = _client(recorder, background=False, max_retries=3)
    client.log_trace(**_trace_args())
    assert len(recorder.requests) == 1


def test_retries_are_bounded() -> None:
    recorder = Recorder([503])
    client = _client(recorder, background=False, max_retries=2)
    client.log_trace(**_trace_args())
    assert len(recorder.requests) == 3


# --- queue ---


def test_full_queue_drops_new_traces_instead_of_growing() -> None:
    recorder = Recorder()
    recorder.release.clear()  # the server hangs until released
    client = _client(recorder, max_queue_size=2)

    for _ in range(10):
        client.log_trace(**_trace_args())

    assert client.dropped_traces >= 7  # one in flight, two queued, the rest dropped
    recorder.release.set()
    assert client.flush(10)


def test_get_trace_waits_for_queued_sends() -> None:
    recorder = Recorder(delay=0.3)
    client = _client(recorder)

    trace_id = client.log_trace(**_trace_args())
    client.get_trace(trace_id)

    methods = [r.method for r in recorder.requests]
    assert methods == ["POST", "GET"]  # the read went out after the write landed


# --- configuration ---


def test_trailing_slash_and_headers() -> None:
    recorder = Recorder()
    client = TraceroClient(
        base_url="http://tracero.test/",
        api_key="k",
        background=False,
        transport=httpx.MockTransport(recorder),
        flush_on_exit_seconds=0,
    )
    client.log_trace(**_trace_args())

    request = recorder.requests[0]
    assert str(request.url) == "http://tracero.test/v1/traces"
    assert request.headers["Authorization"] == "Bearer k"
    assert request.headers["User-Agent"] == f"traceroai-python/{__version__}"


def test_configuration_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("TRACEROAI_API_URL", "http://from-env.test")
    monkeypatch.setenv("TRACEROAI_API_KEY", "env-key")
    client = TraceroClient(flush_on_exit_seconds=0)
    assert client.base_url == "http://from-env.test"
    assert client.api_key == "env-key"


def test_missing_url_is_a_clear_error_unless_disabled(monkeypatch) -> None:
    monkeypatch.delenv("TRACEROAI_API_URL", raising=False)
    with pytest.raises(ValueError, match="TRACEROAI_API_URL"):
        TraceroClient()
    TraceroClient(enabled=False)  # disabled clients don't need one


def test_disabled_client_sends_nothing(monkeypatch) -> None:
    monkeypatch.setenv("TRACEROAI_ENABLED", "false")
    recorder = Recorder()
    client = _client(recorder, background=False)

    trace_id = client.log_trace(**_trace_args())
    with client.trace("q"):
        pass

    assert isinstance(trace_id, UUID)
    assert recorder.requests == []


# --- decorator ---


def test_async_functions_can_be_traced() -> None:
    recorder = Recorder()
    client = _client(recorder, background=False)

    @client.traced(model="m")
    async def answer(query: str):
        await asyncio.sleep(0)
        return "async answer", [{"rank": 1, "chunk_id": "c", "text": "t"}]

    assert asyncio.run(answer("q")) == "async answer"
    assert answer.__name__ == "answer"
    assert json.loads(recorder.requests[0].content)["generation"]["answer"] == "async answer"


def test_sync_decorator_keeps_the_function_name() -> None:
    client = _client(Recorder(), background=False)

    @client.traced(model="m")
    def answer(query: str):
        """Docs."""
        return "a", []

    assert (answer.__name__, answer.__doc__) == ("answer", "Docs.")


def test_explicit_trace_id_is_used() -> None:
    recorder = Recorder()
    client = _client(recorder, background=False)
    chosen = uuid4()
    assert client.log_trace(**_trace_args(), trace_id=chosen) == chosen
    assert recorder.posted_ids() == [str(chosen)]
