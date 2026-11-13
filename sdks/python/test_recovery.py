"""Tests for the self-healing RecoveryAgent (LangGraph).

Run from sdks/python:  python -m pytest test_recovery.py
Needs the recovery extra:  pip install 'traceroai[recovery]'
No live API/LLM — the client, retrieve, and generate are all stubbed.
"""

import pytest

# The recovery feature needs the optional [recovery] extra (langgraph). Skip the
# whole module cleanly when it isn't installed, rather than erroring collection.
pytest.importorskip("langgraph.graph")

from traceroai.recovery import RecoveryAgent  # noqa: E402


class _ScriptedClient:
    """Fake TraceroClient: returns a scripted diagnosis per attempt number.

    `diagnoses` is the list of diagnosis labels to return on attempts 1, 2, 3...
    (the last value repeats if more attempts happen).
    """

    def __init__(self, diagnoses: list[str]) -> None:
        self._diagnoses = diagnoses
        self.posted: list[dict] = []

    def log_trace(self, **payload) -> str:
        self.posted.append(payload)
        return f"trace-{len(self.posted)}"

    def log_trace_sync_eval(self, **payload):
        # Recovery routes on the synchronous judge diagnosis returned here.
        self.posted.append(payload)
        trace_id = f"trace-{len(self.posted)}"
        idx = min(len(self.posted) - 1, len(self._diagnoses) - 1)
        return trace_id, {"label": self._diagnoses[idx], "reason": "scripted", "source": "judge"}

    def get_trace(self, trace_id: str) -> dict:
        n = int(str(trace_id).split("-")[1])
        idx = min(n - 1, len(self._diagnoses) - 1)
        return {
            "diagnosis": {"label": self._diagnoses[idx]},
            "evaluations": {"deep": [{"evaluator_name": "claim_groundedness", "label": "grounded"}]},
        }


def _retrieve(query: str, top_k: int) -> list[dict]:
    return [{"text": f"chunk (k={top_k})"}]


def _generate(query: str, context: str) -> str:
    return "Refunds take 5 to 7 business days."


def test_succeeds_immediately_when_first_attempt_is_healthy() -> None:
    client = _ScriptedClient(["healthy_answer"])
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0)

    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["succeeded"] is True
    assert result["attempts"] == 1
    assert result["diagnosis"] == "healthy_answer"
    assert len(result["trace_ids"]) == 1


def test_recovers_after_retrieval_miss() -> None:
    # attempt 1 fails (retrieval_miss), attempt 2 is healthy
    client = _ScriptedClient(["retrieval_miss", "healthy_answer"])
    seen_top_k: list[int] = []

    def retrieve(query: str, top_k: int) -> list[dict]:
        seen_top_k.append(top_k)
        return [{"text": "x"}]

    agent = RecoveryAgent(client, retrieve=retrieve, generate=_generate, diagnosis_poll_interval=0)
    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["succeeded"] is True
    assert result["attempts"] == 2
    # the recovery lever raised top_k on the retry
    assert seen_top_k == [3, 5]


def test_unsupported_claim_triggers_stricter_generation() -> None:
    client = _ScriptedClient(["unsupported_claim", "healthy_answer"])
    seen_queries: list[str] = []

    def generate(query: str, context: str) -> str:
        seen_queries.append(query)
        return "grounded answer"

    agent = RecoveryAgent(client, retrieve=_retrieve, generate=generate, diagnosis_poll_interval=0)
    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["succeeded"] is True
    # the second generate call got the strict-grounding instruction injected
    assert "ONLY from the provided context" in seen_queries[1]


def test_gives_up_after_max_attempts() -> None:
    client = _ScriptedClient(["unsupported_claim"])  # never healthy
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate, max_attempts=3, diagnosis_poll_interval=0)

    result = agent.run("impossible question", confirm_with_deep_eval=False)

    assert result["succeeded"] is False
    assert result["attempts"] == 3  # bounded — no infinite loop
    assert len(result["trace_ids"]) == 3


def test_wrong_answer_tightens_generation_before_re_retrieving() -> None:
    # A wrong_answer (e.g. a wrong refusal despite good context) should first try a
    # stricter generation prompt, NOT re-retrieve the same context.
    client = _ScriptedClient(["wrong_answer", "healthy_answer"])
    seen_queries: list[str] = []

    def generate(query: str, context: str) -> str:
        seen_queries.append(query)
        return "answer"

    agent = RecoveryAgent(
        client, retrieve=_retrieve, generate=generate, diagnosis_poll_interval=0
    )
    result = agent.run("Is money refunded within 10 days?", confirm_with_deep_eval=False)

    assert result["succeeded"] is True
    # the retry injected the strict-grounding instruction (fix_generation), not a re-retrieve
    assert "ONLY from the provided context" in seen_queries[1]


class _SyncJudgeUnavailableClient:
    """sync deep eval returns no verdict (judge down) -> recovery falls back to the
    stored quick diagnosis from get_trace. Proves the production fallback path."""

    def __init__(self, quick_label: str) -> None:
        self._quick = quick_label

    def log_trace_sync_eval(self, **payload):
        return "trace-1", None  # judge unavailable

    def get_trace(self, trace_id: str) -> dict:
        return {"diagnosis": {"label": self._quick}, "evaluations": {"deep": []}}


def test_falls_back_to_quick_diagnosis_when_sync_judge_unavailable() -> None:
    client = _SyncJudgeUnavailableClient("healthy_answer")
    agent = RecoveryAgent(
        client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0
    )

    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["diagnosis"] == "healthy_answer"   # read from the quick fallback
    assert result["attempts"] == 1


class _SyncTimesOutClient:
    """The sync call fails after the server may already have stored the trace
    (e.g. a read timeout); the fallback send must reuse the attempt's id."""

    def __init__(self) -> None:
        self.sync_ids: list[str] = []
        self.fallback_ids: list[str] = []

    def log_trace_sync_eval(self, **payload):
        self.sync_ids.append(str(payload["trace_id"]))
        raise TimeoutError("read timed out")

    def log_trace(self, **payload):
        self.fallback_ids.append(str(payload["trace_id"]))
        return payload["trace_id"]

    def get_trace(self, trace_id: str) -> dict:
        return {"diagnosis": {"label": "healthy_answer"}, "evaluations": {"deep": []}}


def test_fallback_send_reuses_the_attempt_id() -> None:
    client = _SyncTimesOutClient()
    agent = RecoveryAgent(
        client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0
    )

    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert client.sync_ids == client.fallback_ids  # same id: the server dedupes it
    assert result["trace_ids"] == client.sync_ids
    assert "None" not in result["trace_ids"]


class _DeepEvalClient:
    """Healthy on attempt 1; deep eval 'lands' after `deep_after` get_trace calls."""

    def __init__(self, deep_after: int | None) -> None:
        self._deep_after = deep_after  # None = deep eval never lands
        self._gets = 0

    def log_trace(self, **payload) -> str:
        return "trace-1"

    def log_trace_sync_eval(self, **payload):
        # In-loop routing: judge says healthy on the (only) attempt.
        return "trace-1", {"label": "healthy_answer", "reason": "ok"}

    def get_trace(self, trace_id: str) -> dict:
        # Used by the POST-LOOP confirm_with_deep_eval poll (separate from routing).
        self._gets += 1
        landed = self._deep_after is not None and self._gets >= self._deep_after
        deep = [{"evaluator_name": "claim_groundedness", "label": "grounded"}] if landed else []
        return {"diagnosis": {"label": "healthy_answer"}, "evaluations": {"deep": deep}}


def test_deep_eval_verdict_is_returned_when_it_lands() -> None:
    # Deep eval lands on the first get, so both the in-loop diagnosis read and the
    # post-loop verdict poll see it. poll intervals 0 -> no real sleeps in tests.
    client = _DeepEvalClient(deep_after=1)
    agent = RecoveryAgent(
        client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0
    )

    result = agent.run("How long does a refund take?", deep_eval_interval=0)

    assert result["deep_eval"] is not None
    assert result["deep_eval"][0]["label"] == "grounded"


def test_deep_eval_fails_open_to_none_when_pending() -> None:
    # deep eval never lands -> in-loop read falls back to the quick diagnosis, and the
    # post-loop verdict poll times out -> deep_eval is None, no crash, no hang.
    client = _DeepEvalClient(deep_after=None)
    agent = RecoveryAgent(
        client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0
    )

    result = agent.run("How long does a refund take?", deep_eval_interval=0)

    assert result["succeeded"] is True       # the loop still succeeded
    assert result["deep_eval"] is None        # deep verdict just pending


class _QuickVerdictClient(_ScriptedClient):
    """A server without a judge: every diagnosis is a lexical estimate."""

    def log_trace_sync_eval(self, **payload):
        trace_id, verdict = super().log_trace_sync_eval(**payload)
        return trace_id, {**verdict, "source": "lexical"}


def test_a_quick_check_failure_is_reported_not_retried() -> None:
    client = _QuickVerdictClient(["retrieval_miss", "healthy_answer"])
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0)

    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["attempts"] == 1  # no retry spent on an unverified failure
    assert result["succeeded"] is False
    assert (result["diagnosis"], result["diagnosis_source"]) == ("retrieval_miss", "lexical")


def test_retrying_on_quick_checks_is_opt_in() -> None:
    client = _QuickVerdictClient(["retrieval_miss", "healthy_answer"])
    agent = RecoveryAgent(
        client,
        retrieve=_retrieve,
        generate=_generate,
        diagnosis_poll_interval=0,
        retry_on_quick_diagnosis=True,
    )

    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["attempts"] == 2
    assert result["succeeded"] is True


def test_judge_verdicts_report_their_source() -> None:
    client = _ScriptedClient(["unsupported_claim", "healthy_answer"])
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0)

    result = agent.run("q", confirm_with_deep_eval=False)

    assert result["diagnosis_source"] == "judge" and result["attempts"] == 2


# --- run ids, recorded levers, and the caller's own failures ---


def test_attempts_share_a_run_id_and_record_top_k() -> None:
    client = _ScriptedClient(["retrieval_miss", "healthy_answer"])
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0)

    agent.run("q", confirm_with_deep_eval=False)
    agent.run("q", confirm_with_deep_eval=False)

    metas = [p["metadata"] for p in client.posted]
    first, second = metas[0]["recovery_run_id"], metas[2]["recovery_run_id"]
    assert metas[1]["recovery_run_id"] == first  # one run, two attempts
    assert first != second  # the same question asked again is a new run
    assert [m["top_k"] for m in metas[:2]] == [3, 5]
    assert [p["retrieval"]["config"]["final_top_k"] for p in client.posted[:2]] == [3, 5]


def test_without_a_rewriter_the_question_is_not_altered() -> None:
    client = _ScriptedClient(["retrieval_miss", "healthy_answer"])
    seen: list[str] = []

    def retrieve(query: str, top_k: int) -> list[dict]:
        seen.append(query)
        return [{"text": "x"}]

    agent = RecoveryAgent(client, retrieve=retrieve, generate=_generate, diagnosis_poll_interval=0)
    agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert seen == ["How long does a refund take?"] * 2
    assert "rewritten" not in client.posted[1]["query"]


def test_a_supplied_rewriter_is_used_and_recorded() -> None:
    client = _ScriptedClient(["retrieval_miss", "healthy_answer"])
    seen: list[str] = []

    def retrieve(query: str, top_k: int) -> list[dict]:
        seen.append(query)
        return [{"text": "x"}]

    agent = RecoveryAgent(
        client,
        retrieve=retrieve,
        generate=_generate,
        diagnosis_poll_interval=0,
        rewrite=lambda q: f"refund processing time ({q})",
    )
    agent.run("How long?", confirm_with_deep_eval=False)

    assert seen == ["How long?", "refund processing time (How long?)"]
    assert client.posted[1]["query"] == {
        "original": "How long?",
        "rewritten": "refund processing time (How long?)",
        "rewrite_changed": True,
    }


def test_a_failing_rewriter_keeps_the_question() -> None:
    client = _ScriptedClient(["retrieval_miss", "healthy_answer"])

    def broken_rewrite(question: str) -> str:
        raise RuntimeError("rewriter down")

    agent = RecoveryAgent(
        client, retrieve=_retrieve, generate=_generate, diagnosis_poll_interval=0,
        rewrite=broken_rewrite,
    )
    result = agent.run("q", confirm_with_deep_eval=False)

    assert result["succeeded"] is True
    assert "rewritten" not in client.posted[1]["query"]


@pytest.mark.parametrize("stage", ["retrieve", "generate"])
def test_a_failure_in_your_pipeline_is_traced_then_raised(stage: str) -> None:
    client = _ScriptedClient(["healthy_answer"])
    logged: list[dict] = []
    client.log_trace = lambda **payload: logged.append(payload) or "trace-err"  # type: ignore[method-assign]

    def boom(*args):
        raise ConnectionError("vector store unreachable")

    agent = RecoveryAgent(
        client,
        retrieve=boom if stage == "retrieve" else _retrieve,
        generate=boom if stage == "generate" else _generate,
        diagnosis_poll_interval=0,
    )

    with pytest.raises(ConnectionError, match="vector store unreachable"):
        agent.run("q", confirm_with_deep_eval=False)

    assert len(logged) == 1  # the failed attempt was recorded, without a judge call
    assert logged[0]["status"] == "error"
    assert logged[0]["generation"]["answered"] is False
    assert f"{stage} failed" in logged[0]["generation"]["answer"]
    assert client.posted == []  # nothing sent for judging
