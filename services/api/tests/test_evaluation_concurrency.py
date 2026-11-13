"""Background evaluation must not overwrite writes that land while it runs, and
must not hold database connections while it waits on the LLM provider."""

from uuid import UUID

from fastapi.testclient import TestClient

import app.api.routes.traces as traces_route
from app.db.session import engine
from app.main import app
from app.services.deep_evaluation import run_deep_evaluation
from tests.test_deep_groundedness import StubJudge, make_trace_payload

client = TestClient(app)


class _JudgeWithSideEffect(StubJudge):
    """Runs `during` while the judge is "thinking", i.e. mid-evaluation."""

    def __init__(self, during) -> None:
        self._during = during

    def judge_claim_groundedness(self, answer: str, context: str):
        self._during()
        return super().judge_claim_groundedness(answer, context)


def _ingest(monkeypatch) -> str:
    # Keep the ingest's own background evaluation out of the way.
    monkeypatch.setattr(traces_route, "enqueue_deep_eval_request", lambda trace_id: True)
    return client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]


def test_feedback_added_during_evaluation_is_kept(monkeypatch) -> None:
    trace_id = _ingest(monkeypatch)

    def add_feedback() -> None:
        response = client.post(
            f"/v1/traces/{trace_id}/feedback",
            json={"rating": "thumbs_down", "comment": "arrived mid-evaluation"},
        )
        assert response.status_code == 201

    run_deep_evaluation(UUID(trace_id), judge=_JudgeWithSideEffect(add_feedback))

    trace = client.get(f"/v1/traces/{trace_id}").json()
    assert [f["comment"] for f in trace["feedback"]] == ["arrived mid-evaluation"]
    assert {r["evaluator_name"] for r in trace["evaluations"]["deep"]} == {
        "deep_context_relevance",
        "claim_groundedness",
        "deep_answer_relevance",
    }


def test_sync_ingest_holds_no_connection_while_evaluating(monkeypatch) -> None:
    # The request's own session must have released its connection by the time
    # the inline judge runs (it used to keep one open after save()).
    checked_out: list[int] = []

    def evaluate(trace_id, **kwargs) -> None:
        checked_out.append(engine.pool.checkedout())
        run_deep_evaluation(trace_id, judge=StubJudge(), **kwargs)

    monkeypatch.setattr(traces_route, "run_deep_evaluation", evaluate)
    response = client.post("/v1/traces?sync_deep_eval=true", json=make_trace_payload())

    assert response.status_code == 202
    assert checked_out == [0]


def test_fallback_evaluation_runs_on_its_own_threads_and_never_raises(monkeypatch) -> None:
    import threading

    from app.services import fallback_evaluation

    seen: list[str] = []

    def fake_evaluation(trace_id) -> None:
        seen.append(threading.current_thread().name)
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(fallback_evaluation, "run_deep_evaluation", fake_evaluation)

    future = fallback_evaluation.submit_fallback_evaluation(UUID(int=1))

    assert future.result(timeout=5) is None  # logged, not raised
    assert seen[0].startswith("deep-eval-fallback")


def test_inline_judge_has_a_short_timeout_and_no_retries(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.services.deep_evaluation import (
        INLINE_JUDGE_TIMEOUT_SECONDS,
        _build_default_judge,
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    inline = _build_default_judge(settings, inline=True)._client
    background = _build_default_judge(settings)._client

    assert (inline.timeout, inline.max_retries) == (INLINE_JUDGE_TIMEOUT_SECONDS, 0)
    assert background.max_retries == 2


def test_no_database_connection_is_held_while_the_judge_runs(monkeypatch) -> None:
    trace_id = _ingest(monkeypatch)
    checked_out: list[int] = []

    def record_pool_usage() -> None:
        checked_out.append(engine.pool.checkedout())

    run_deep_evaluation(UUID(trace_id), judge=_JudgeWithSideEffect(record_pool_usage))

    assert checked_out == [0]
