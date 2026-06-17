"""Tests for the self-healing RecoveryAgent (LangGraph).

Run from sdks/python:  python -m pytest test_recovery.py
Needs the recovery extra:  pip install 'traceroai[recovery]'
No live API/LLM — the client, retrieve, and generate are all stubbed.
"""

from traceroai.recovery import RecoveryAgent


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

    def get_trace(self, trace_id: str) -> dict:
        n = int(str(trace_id).split("-")[1])
        idx = min(n - 1, len(self._diagnoses) - 1)
        return {
            "diagnosis": {"label": self._diagnoses[idx]},
            "evaluations": {"deep": []},
        }


def _retrieve(query: str, top_k: int) -> list[dict]:
    return [{"text": f"chunk (k={top_k})"}]


def _generate(query: str, context: str) -> str:
    return "Refunds take 5 to 7 business days."


def test_succeeds_immediately_when_first_attempt_is_healthy() -> None:
    client = _ScriptedClient(["healthy_answer"])
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate)

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

    agent = RecoveryAgent(client, retrieve=retrieve, generate=_generate)
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

    agent = RecoveryAgent(client, retrieve=_retrieve, generate=generate)
    result = agent.run("How long does a refund take?", confirm_with_deep_eval=False)

    assert result["succeeded"] is True
    # the second generate call got the strict-grounding instruction injected
    assert "ONLY from the provided context" in seen_queries[1]


def test_gives_up_after_max_attempts() -> None:
    client = _ScriptedClient(["unsupported_claim"])  # never healthy
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate, max_attempts=3)

    result = agent.run("impossible question", confirm_with_deep_eval=False)

    assert result["succeeded"] is False
    assert result["attempts"] == 3  # bounded — no infinite loop
    assert len(result["trace_ids"]) == 3


class _DeepEvalClient:
    """Healthy on attempt 1; deep eval 'lands' after `deep_after` get_trace calls."""

    def __init__(self, deep_after: int | None) -> None:
        self._deep_after = deep_after  # None = deep eval never lands
        self._gets = 0

    def log_trace(self, **payload) -> str:
        return "trace-1"

    def get_trace(self, trace_id: str) -> dict:
        self._gets += 1
        landed = self._deep_after is not None and self._gets >= self._deep_after
        deep = [{"evaluator_name": "claim_groundedness", "label": "grounded"}] if landed else []
        return {"diagnosis": {"label": "healthy_answer"}, "evaluations": {"deep": deep}}


def test_deep_eval_verdict_is_returned_when_it_lands() -> None:
    # get #1 = quick diagnosis (loop); deep lands by get #2 (the poll).
    client = _DeepEvalClient(deep_after=2)
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate)

    result = agent.run("How long does a refund take?", deep_eval_interval=0)

    assert result["deep_eval"] is not None
    assert result["deep_eval"][0]["label"] == "grounded"


def test_deep_eval_fails_open_to_none_when_pending() -> None:
    # deep eval never lands -> poll times out -> deep_eval is None, no crash.
    client = _DeepEvalClient(deep_after=None)
    agent = RecoveryAgent(client, retrieve=_retrieve, generate=_generate)

    result = agent.run("How long does a refund take?", deep_eval_interval=0)

    assert result["succeeded"] is True       # the loop still succeeded
    assert result["deep_eval"] is None        # deep verdict just pending
