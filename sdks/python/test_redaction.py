"""redact=: sensitive data is removed before a trace leaves the application.

Run from sdks/python:  python -m pytest test_redaction.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

import httpx
import pytest

from traceroai import AsyncTraceroClient, TraceroClient, TraceroError
from traceroai.redaction import mask_emails, redact_strings

BASE = "http://tracero.test"


class Server:
    """A mock server that keeps every trace it's sent."""

    def __init__(self) -> None:
        self.bodies: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        return httpx.Response(202, json={"trace_id": self.bodies[-1]["trace_id"], "diagnosis": None})


def _trace() -> dict:
    return {
        "query": {"original": "Can you refund asha@example.com for order 17?"},
        "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c1", "text": "Contact billing@shop.in for refunds."}]},
        "generation": {"model": "gpt-4o-mini", "answer": "I've asked billing@shop.in to refund asha@example.com."},
        "metadata": {"user": "asha@example.com"},
    }


def _client(server: Server, **kwargs) -> TraceroClient:
    return TraceroClient(base_url=BASE, background=False, transport=httpx.MockTransport(server), **kwargs)


def test_emails_are_masked_everywhere_user_text_appears() -> None:
    server = Server()
    client = _client(server, redact=redact_strings(mask_emails))
    trace_id = client.log_trace(**_trace())

    sent = server.bodies[0]
    assert "@" not in json.dumps(sent["query"]) + json.dumps(sent["retrieval"]) + json.dumps(sent["generation"])
    assert sent["query"]["original"] == "Can you refund [email] for order 17?"
    assert sent["retrieval"]["chunks"][0]["text"] == "Contact [email] for refunds."
    assert sent["metadata"] == {"user": "[email]"}
    # Structure is untouched: the id, the model, the chunk id.
    assert sent["trace_id"] == str(trace_id)
    assert sent["generation"]["model"] == "gpt-4o-mini"
    assert sent["retrieval"]["chunks"][0]["chunk_id"] == "c1"


def test_returning_none_drops_the_trace() -> None:
    server = Server()
    client = _client(server, redact=lambda trace: None if "refund" in trace["query"]["original"] else trace)
    client.log_trace(**_trace())
    assert server.bodies == []
    assert client.redaction_failures == 0  # a deliberate drop isn't a failure


@pytest.mark.parametrize(
    "redactor",
    [lambda trace: 1 / 0, lambda trace: "not a dict"],
    ids=["raises", "returns a string"],
)
def test_a_failing_redactor_drops_the_trace_and_never_raises(redactor, caplog) -> None:
    server = Server()
    client = _client(server, redact=redactor)
    with caplog.at_level(logging.WARNING, logger="traceroai"):
        client.log_trace(**_trace())
        client.log_trace(**_trace())
    assert server.bodies == []  # never sent unredacted
    assert client.redaction_failures == 2
    assert "not sent unredacted" in caplog.text


def test_the_redactor_cannot_change_the_trace_id() -> None:
    server = Server()

    def rename(trace: dict) -> dict:
        trace["trace_id"] = str(uuid4())
        return trace

    client = _client(server, redact=rename)
    trace_id = client.log_trace(**_trace())
    assert server.bodies[0]["trace_id"] == str(trace_id)


def test_the_background_sender_only_ever_holds_redacted_traces() -> None:
    server = Server()
    client = TraceroClient(base_url=BASE, transport=httpx.MockTransport(server), redact=redact_strings(mask_emails))
    client.log_trace(**_trace())
    assert client.flush(5)
    assert server.bodies[0]["query"]["original"] == "Can you refund [email] for order 17?"


def test_sync_eval_raises_rather_than_sending_unredacted() -> None:
    server = Server()
    client = _client(server, redact=lambda trace: 1 / 0)
    with pytest.raises(TraceroError, match="not sent"):
        client.log_trace_sync_eval(**_trace())
    assert server.bodies == []

    dropping = _client(server, redact=lambda trace: None)
    with pytest.raises(TraceroError, match="dropped by redact"):
        dropping.log_trace_sync_eval(**_trace())
    assert server.bodies == []


def test_the_async_client_redacts_the_same_way() -> None:
    server = Server()

    async def run() -> None:
        client = AsyncTraceroClient(
            base_url=BASE, transport=httpx.MockTransport(server), redact=redact_strings(mask_emails)
        )
        client.log_trace(**_trace())
        failing = AsyncTraceroClient(base_url=BASE, transport=httpx.MockTransport(server), redact=lambda t: 1 / 0)
        failing.log_trace(**_trace())
        await client.flush()
        await failing.flush()
        assert failing.redaction_failures == 1

    asyncio.run(run())
    assert len(server.bodies) == 1
    assert server.bodies[0]["generation"]["answer"] == "I've asked [email] to refund [email]."
