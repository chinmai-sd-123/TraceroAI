"""Every diagnosis says which evaluation produced it, and every trace says where
its LLM-judge evaluation stands."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.api.routes.traces as traces_route
from app.core.config import get_settings
from app.main import app
from app.schemas.traces import Trace
from app.services.deep_evaluation import run_deep_evaluation
from tests.test_background_evaluation import StubEmbedder
from tests.test_deep_groundedness import StubJudge, make_trace_payload

client = TestClient(app)


class FailingJudge(StubJudge):
    def judge_claim_groundedness(self, answer: str, context: str):
        raise ValueError("unparseable verdict")


def _ingest() -> str:
    return client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]


def _trace(trace_id: str) -> dict:
    return client.get(f"/v1/traces/{trace_id}").json()


@pytest.fixture
def judge_key(monkeypatch):
    """A configured judge, with the queue standing in for the worker."""
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test")
    queued: list = []
    monkeypatch.setattr(
        traces_route, "enqueue_deep_eval_request", lambda trace_id: queued.append(trace_id) or True
    )
    return queued


def test_ingest_diagnosis_is_lexical() -> None:
    assert _trace(_ingest())["diagnosis"]["source"] == "lexical"


def test_with_a_judge_the_trace_starts_pending_and_is_queued(judge_key) -> None:
    trace_id = _ingest()

    assert _trace(trace_id)["evaluations"]["deep_status"] == "pending"
    assert [str(t) for t in judge_key] == [trace_id]


def test_without_a_judge_nothing_is_queued(monkeypatch) -> None:
    queued: list = []
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda t: queued.append(t))
    monkeypatch.setattr(traces_route, "submit_fallback_evaluation", lambda t: queued.append(t))

    trace_id = _ingest()

    assert queued == []
    assert _trace(trace_id)["evaluations"]["deep_status"] == "skipped"


def test_judge_verdict_is_marked_judge_and_complete() -> None:
    trace_id = _ingest()

    run_deep_evaluation(UUID(trace_id), judge=StubJudge())

    trace = _trace(trace_id)
    assert trace["diagnosis"]["source"] == "judge"
    assert trace["evaluations"]["deep_status"] == "complete"


class BrokenJudge(StubJudge):
    def _fail(self, *args, **kwargs):
        raise ValueError("unparseable verdict")

    judge_claim_groundedness = judge_context_relevance = judge_answer_relevance = _fail


def test_one_failed_judge_call_is_partial_and_the_rest_still_count() -> None:
    trace_id = _ingest()

    run_deep_evaluation(UUID(trace_id), judge=FailingJudge())

    trace = _trace(trace_id)
    assert trace["evaluations"]["deep_status"] == "partial"
    labels = {r["evaluator_name"]: r["label"] for r in trace["evaluations"]["deep"]}
    assert labels == {
        "deep_context_relevance": "relevant",
        "claim_groundedness": "error",
        "deep_answer_relevance": "relevant",
    }
    assert trace["diagnosis"]["source"] == "judge"


def test_every_judge_call_failing_is_failed_and_keeps_the_quick_diagnosis() -> None:
    trace_id = _ingest()
    before = _trace(trace_id)["diagnosis"]

    run_deep_evaluation(UUID(trace_id), judge=BrokenJudge())

    trace = _trace(trace_id)
    assert trace["evaluations"]["deep_status"] == "failed"
    assert trace["diagnosis"] == before  # still the lexical diagnosis, still labelled so


def test_a_bad_verdict_is_retried_once() -> None:
    class FlakyJudge(StubJudge):
        calls = 0

        def judge_claim_groundedness(self, answer, context):
            FlakyJudge.calls += 1
            if FlakyJudge.calls == 1:
                raise ValueError("Judge returned no parsed verdict.")
            return super().judge_claim_groundedness(answer, context)

    trace_id = _ingest()
    run_deep_evaluation(UUID(trace_id), judge=FlakyJudge())

    assert FlakyJudge.calls == 2
    assert _trace(trace_id)["evaluations"]["deep_status"] == "complete"


def test_semantic_pass_is_marked_embedding(monkeypatch) -> None:
    trace_id = _ingest()
    monkeypatch.setattr(get_settings(), "deep_eval_enabled", False)

    run_deep_evaluation(UUID(trace_id), embedder=StubEmbedder())

    trace = _trace(trace_id)
    assert trace["diagnosis"]["source"] == "embedding"
    assert trace["evaluations"]["deep_status"] == "skipped"


def test_sync_response_carries_the_source(monkeypatch) -> None:
    monkeypatch.setattr(
        traces_route,
        "run_deep_evaluation",
        lambda trace_id, **kwargs: run_deep_evaluation(trace_id, judge=StubJudge(), **kwargs),
    )

    diagnosis = client.post(
        "/v1/traces?sync_deep_eval=true", json=make_trace_payload()
    ).json()["diagnosis"]

    assert diagnosis["source"] == "judge"


def test_traces_stored_before_provenance_still_load() -> None:
    legacy = make_trace_payload() | {
        "diagnosis": {"label": "healthy_answer", "reason": "old"},
        "evaluations": {"quick": [], "deep": []},
    }
    trace = Trace(**legacy)
    assert trace.diagnosis.source is None
    assert trace.evaluations.deep_status is None
