"""AsyncTraceroClient: same guarantees as the sync client, on the event loop."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

import httpx

from traceroai import AsyncTraceroClient, __version__

BASE = "http://tracero.test"


def _client(handler, **kwargs) -> AsyncTraceroClient:
    kwargs.setdefault("retry_backoff_seconds", 0.0)
    return AsyncTraceroClient(base_url=BASE, transport=httpx.MockTransport(handler), **kwargs)


def _minimal(**overrides):
    body = {
        "query": {"original": "q"},
        "retrieval": {"chunks": [{"text": "a chunk"}]},
        "generation": {"answer": "an answer", "model": "m"},
    }
    body.update(overrides)
    return body


def test_log_trace_returns_at_once_and_delivers_in_the_background():
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, json={"trace_id": json.loads(request.content)["trace_id"]})

    async def scenario():
        client = _client(handler, api_key="k1")
        trace_id = client.log_trace(**_minimal())
        assert seen == []  # nothing sent until the loop runs the task
        assert await client.flush(1) is True
        await client.aclose()
        return trace_id

    trace_id = asyncio.run(scenario())
    assert isinstance(trace_id, UUID)
    assert len(seen) == 1
    body = json.loads(seen[0].content)
    assert body["trace_id"] == str(trace_id)
    assert body["retrieval"]["chunks"][0]["rank"] == 1  # filled client-side, like the sync client
    assert seen[0].headers["authorization"] == "Bearer k1"
    assert seen[0].headers["user-agent"] == f"traceroai-python/{__version__}"


def test_temporary_failures_are_retried():
    statuses = iter([503, 429, 202])
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(next(statuses))

    async def scenario():
        client = _client(handler, max_retries=3)
        client.log_trace(**_minimal())
        await client.aclose()

    asyncio.run(scenario())
    assert calls == 3


def test_a_rejected_trace_is_not_retried_and_never_raises(caplog):
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(422, json={"detail": "bad"})

    async def scenario():
        client = _client(handler, max_retries=3)
        client.log_trace(**_minimal())
        assert await client.flush(1) is True
        await client.aclose()

    with caplog.at_level(logging.WARNING, logger="traceroai"):
        asyncio.run(scenario())
    assert calls == 1
    assert "HTTP 422" in caplog.text


def test_an_unreachable_server_never_raises_into_the_app(caplog):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async def scenario():
        client = _client(handler, max_retries=1)
        with client.trace("q") as t:
            t.log_generation("a", model="m")
        await client.aclose()
        return t.trace_id

    with caplog.at_level(logging.WARNING, logger="traceroai"):
        asyncio.run(scenario())
    assert "ConnectError" in caplog.text


def test_trace_works_with_and_async_with():
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(202)

    async def scenario():
        client = _client(handler)
        with client.trace("plain with") as t1:
            t1.log_retrieval([{"text": "c"}])
            await asyncio.sleep(0)
            t1.log_generation("first", model="m")
        async with client.trace("async with") as t2:
            t2.log_generation("second", model="m")
        await client.aclose()
        return t1.trace_id, t2.trace_id

    ids = asyncio.run(scenario())
    assert {b["trace_id"] for b in bodies} == {str(i) for i in ids}
    by_query = {b["query"]["original"]: b for b in bodies}
    assert by_query["plain with"]["generation"]["answered"] is True
    assert "retrieval_ms" in by_query["plain with"]["latency"]
    assert by_query["async with"]["generation"]["answer"] == "second"


def test_an_exception_in_the_block_is_recorded_and_not_swallowed():
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(202)

    async def scenario():
        client = _client(handler)
        try:
            async with client.trace("q"):
                raise RuntimeError("model timed out")
        except RuntimeError:
            pass
        else:
            raise AssertionError("the caller's exception must propagate")
        await client.aclose()

    asyncio.run(scenario())
    assert bodies[0]["generation"]["answered"] is False
    assert "model timed out" in bodies[0]["generation"]["answer"]


def test_traced_decorator_wraps_an_async_function():
    bodies: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(202)

    async def scenario():
        client = _client(handler)

        @client.traced(model="m")
        async def answer(query: str):
            return f"answer to {query}", [{"text": "c"}]

        result = await answer("why?")
        await client.aclose()
        return result

    assert asyncio.run(scenario()) == "answer to why?"
    assert bodies[0]["query"]["original"] == "why?"


def test_without_a_running_loop_the_trace_is_dropped_with_a_warning(caplog):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("nothing should be sent")

    client = _client(handler)
    with caplog.at_level(logging.WARNING, logger="traceroai"):
        trace_id = client.log_trace(**_minimal())
    assert isinstance(trace_id, UUID)
    assert "running event loop" in caplog.text


def test_too_many_traces_in_flight_are_dropped_not_queued_without_bound():
    release = asyncio.Event

    async def scenario():
        gate = release()

        async def handler(request: httpx.Request) -> httpx.Response:
            await gate.wait()
            return httpx.Response(202)

        client = _client(handler, max_pending=2)
        for _ in range(5):
            client.log_trace(**_minimal())
        dropped = client.dropped_traces
        gate.set()
        await client.aclose()
        return dropped

    assert asyncio.run(scenario()) == 3


def test_disabled_client_sends_nothing():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("nothing should be sent")

    async def scenario():
        client = AsyncTraceroClient(enabled=False, transport=httpx.MockTransport(handler))
        trace_id = client.log_trace(**_minimal())
        await client.aclose()
        return trace_id

    assert isinstance(asyncio.run(scenario()), UUID)


def test_get_trace_sends_pending_traces_first():
    stored: dict[str, dict] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            stored[body["trace_id"]] = body
            return httpx.Response(202)
        trace_id = request.url.path.rsplit("/", 1)[-1]
        if trace_id in stored:
            return httpx.Response(200, json=stored[trace_id])
        return httpx.Response(404)

    async def scenario():
        async with _client(handler) as client:
            trace_id = client.log_trace(**_minimal())
            return await client.get_trace(trace_id)

    assert asyncio.run(scenario())["generation"]["answer"] == "an answer"


def test_log_trace_sync_eval_returns_the_judge_verdict():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["sync_deep_eval"] == "true"
        body = json.loads(request.content)
        return httpx.Response(
            202, json={"trace_id": body["trace_id"], "diagnosis": {"label": "healthy", "reason": "ok"}}
        )

    async def scenario():
        async with _client(handler) as client:
            return await client.log_trace_sync_eval(**_minimal())

    trace_id, diagnosis = asyncio.run(scenario())
    assert isinstance(trace_id, UUID)
    assert diagnosis == {"label": "healthy", "reason": "ok"}
