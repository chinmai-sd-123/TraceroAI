"""The deep-eval worker against a real Redis.

Uses TRACEROAI_TEST_REDIS_URL (default: database 15 on local Redis) with stream
names unique to each test. Skipped when no Redis is reachable.
"""

import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
import redis
from fastapi.testclient import TestClient

import app.api.routes.traces as traces_route
import app.worker as worker_module
from app.core.config import get_settings
from app.main import app
from app.services import deep_eval_queue
from app.services.deep_evaluation import TransientEvaluationError
from app.worker import DeepEvalWorker
from tests.test_deep_groundedness import make_trace_payload

TEST_REDIS_URL = os.environ.get("TRACEROAI_TEST_REDIS_URL", "redis://localhost:6379/15")
client = TestClient(app)


@pytest.fixture
def redis_client(monkeypatch):
    if urlsplit(TEST_REDIS_URL).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("TRACEROAI_TEST_REDIS_URL must point at a local Redis")
    connection = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True, socket_timeout=5)
    try:
        connection.ping()
    except redis.exceptions.RedisError:
        pytest.skip("no Redis at TRACEROAI_TEST_REDIS_URL")

    suffix = uuid4().hex[:8]
    names = {
        "STREAM": f"test:{suffix}:stream",
        "GROUP": f"test:{suffix}:group",
        "DEAD_LETTER_STREAM": f"test:{suffix}:dead",
        "LEGACY_LIST": f"test:{suffix}:legacy",
    }
    for module in (worker_module, deep_eval_queue):
        for name, value in names.items():
            monkeypatch.setattr(module, name, value, raising=False)
    # enqueue_deep_eval_request reads the URL from settings.
    monkeypatch.setattr(get_settings(), "redis_url", TEST_REDIS_URL)

    yield connection
    connection.delete(*names.values())


def _worker(connection, handler, **kwargs) -> DeepEvalWorker:
    worker = DeepEvalWorker(connection, "test-consumer", handler=handler, block_ms=100, **kwargs)
    worker.ensure_group()
    return worker


def _pending_trace(monkeypatch) -> str:
    """A stored trace whose judge evaluation is still to come."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test")
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]
    assert client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["deep_status"] == "pending"
    return trace_id


def test_a_finished_job_is_acknowledged(redis_client) -> None:
    handled: list = []
    worker = _worker(redis_client, lambda trace_id, **_: handled.append(trace_id))
    trace_id = uuid4()
    redis_client.xadd(worker_module.STREAM, {"trace_id": str(trace_id)})

    jobs = worker.read_new()
    assert [worker.handle(job) for job in jobs] == ["acked"]
    assert handled == [trace_id]
    assert redis_client.xpending(worker_module.STREAM, worker_module.GROUP)["pending"] == 0


def test_a_transient_failure_stays_pending_for_retry(redis_client) -> None:
    def rate_limited(trace_id, **_):
        raise TransientEvaluationError("429")

    worker = _worker(redis_client, rate_limited)
    redis_client.xadd(worker_module.STREAM, {"trace_id": str(uuid4())})

    assert [worker.handle(job) for job in worker.read_new()] == ["retry"]
    assert redis_client.xpending(worker_module.STREAM, worker_module.GROUP)["pending"] == 1


def test_an_abandoned_job_is_reclaimed_by_another_worker(redis_client) -> None:
    redis_client.xadd(worker_module.STREAM, {"trace_id": str(uuid4())})
    crashed = _worker(redis_client, lambda *a, **k: None)
    crashed.consumer = "crashed-consumer"
    assert len(crashed.read_new()) == 1  # read, never acknowledged

    survivor = _worker(redis_client, lambda *a, **k: None, visibility_timeout_ms=0)
    jobs = survivor.reclaim_stale()

    assert len(jobs) == 1 and jobs[0].deliveries == 2
    assert survivor.handle(jobs[0]) == "acked"


def test_the_last_failed_attempt_dead_letters_and_marks_the_trace_failed(
    redis_client, monkeypatch
) -> None:
    trace_id = _pending_trace(monkeypatch)

    def broken(trace_id, **_):
        raise RuntimeError("database fell over")

    worker = _worker(redis_client, broken, max_deliveries=1)
    redis_client.xadd(worker_module.STREAM, {"trace_id": trace_id})

    assert [worker.handle(job) for job in worker.read_new()] == ["dead_lettered"]
    assert redis_client.xlen(worker_module.DEAD_LETTER_STREAM) == 1
    trace = client.get(f"/v1/traces/{trace_id}").json()
    assert trace["evaluations"]["deep_status"] == "failed"


def test_a_malformed_job_is_dead_lettered_without_retries(redis_client) -> None:
    worker = _worker(redis_client, lambda *a, **k: None)
    redis_client.xadd(worker_module.STREAM, {"trace_id": "not-a-uuid"})

    assert [worker.handle(job) for job in worker.read_new()] == ["dead_lettered"]


def test_sweep_requeues_a_trace_whose_job_was_lost(redis_client, monkeypatch) -> None:
    trace_id = _pending_trace(monkeypatch)  # pending, but no job anywhere
    worker = _worker(redis_client, lambda *a, **k: None, stalled_after_seconds=0)

    assert worker.requeue_stalled() >= 1
    queued = {
        fields["trace_id"]
        for _, fields in redis_client.xrange(worker_module.STREAM)
    }
    assert trace_id in queued


def test_sweep_waits_while_jobs_are_still_queued(redis_client, monkeypatch) -> None:
    _pending_trace(monkeypatch)
    worker = _worker(redis_client, lambda *a, **k: None, stalled_after_seconds=0)
    redis_client.xadd(worker_module.STREAM, {"trace_id": str(uuid4())})  # backlog

    assert worker.requeue_stalled() == 0


def test_sweep_does_nothing_without_a_judge(redis_client, monkeypatch) -> None:
    _pending_trace(monkeypatch)
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
    worker = _worker(redis_client, lambda *a, **k: None, stalled_after_seconds=0)

    assert worker.requeue_stalled() == 0
