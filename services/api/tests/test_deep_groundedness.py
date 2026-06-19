from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.services.deep_evaluation import run_deep_evaluation
from app.services.llm_judge import ClaimGroundednessVerdict, JudgedClaim, RelevanceVerdict

client = TestClient(app)


class StubJudge:
    def judge_claim_groundedness(self, answer: str, context: str) -> ClaimGroundednessVerdict:
        return ClaimGroundednessVerdict(
            claims=[
                JudgedClaim(
                    claim="admins cannot change the region",
                    supported=True,
                    reason="entailed by the context",
                )
            ]
        )

    def judge_context_relevance(self, query: str, context: str) -> RelevanceVerdict:
        return RelevanceVerdict(relevant=True, reason="context addresses the query")

    def judge_answer_relevance(self, query: str, answer: str) -> RelevanceVerdict:
        return RelevanceVerdict(relevant=True, reason="answer addresses the query")


def make_trace_payload() -> dict:
    return {
        "query": {"original": "Can admins change the workspace region?"},
        "retrieval": {
            "chunks": [
                {
                    "rank": 1,
                    "chunk_id": "c1",
                    "text": "Customers cannot change a workspace region after creation.",
                }
            ]
        },
        "generation": {
            "model": "gpt-4o-mini",
            "answer": "No, admins cannot change the region [1].",
        },
    }


def test_deep_evaluation_populates_all_deep_results() -> None:
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]

    run_deep_evaluation(UUID(trace_id), judge=StubJudge())

    deep = client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["deep"]
    by_name = {result["evaluator_name"]: result for result in deep}

    assert set(by_name) == {
        "deep_context_relevance",
        "claim_groundedness",
        "deep_answer_relevance",
    }
    assert by_name["claim_groundedness"]["label"] == "grounded"
    assert by_name["claim_groundedness"]["details"]["claims"][0]["supported"] is True
    assert by_name["deep_context_relevance"]["label"] == "relevant"
    assert by_name["deep_answer_relevance"]["label"] == "relevant"


class UngroundedStubJudge(StubJudge):
    """A judge that rules the answer NOT grounded — used to prove the judge can also
    flip a diagnosis the other way (healthy quick eval -> unsupported_claim)."""

    def judge_claim_groundedness(self, answer: str, context: str) -> ClaimGroundednessVerdict:
        return ClaimGroundednessVerdict(
            claims=[JudgedClaim(claim="X", supported=False, reason="not in context")]
        )


def test_deep_evaluation_overwrites_diagnosis_with_judge_verdict() -> None:
    """Deep eval must re-diagnose from the judge's verdict, not leave the quick one.
    The judge here rules everything supported/relevant -> healthy_answer."""
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]

    run_deep_evaluation(UUID(trace_id), judge=StubJudge())

    trace = client.get(f"/v1/traces/{trace_id}").json()
    assert trace["diagnosis"]["label"] == "healthy_answer"
    # the diagnosis reason should reflect that it came from the (deep) checks passing
    assert trace["evaluations"]["deep"]  # judge results are present


def test_deep_judge_can_flip_diagnosis_to_unsupported_claim() -> None:
    """When the judge finds claims unsupported, the diagnosis becomes unsupported_claim
    even if the quick eval happened to pass — the judge is authoritative either way."""
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]

    run_deep_evaluation(UUID(trace_id), judge=UngroundedStubJudge())

    diagnosis = client.get(f"/v1/traces/{trace_id}").json()["diagnosis"]["label"]
    assert diagnosis == "unsupported_claim"


def test_sync_deep_eval_returns_judge_diagnosis_in_response(monkeypatch) -> None:
    """With ?sync_deep_eval=true the judge runs inline and the corrected diagnosis is
    in the POST response — so the recovery agent can route without polling."""
    import app.api.routes.traces as traces_route

    # Force the inline deep eval to use the stub judge (no real LLM / key needed).
    monkeypatch.setattr(
        traces_route,
        "run_deep_evaluation",
        lambda trace_id: run_deep_evaluation(trace_id, judge=StubJudge()),
    )

    resp = client.post("/v1/traces?sync_deep_eval=true", json=make_trace_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert body["diagnosis"] is not None
    assert body["diagnosis"]["label"] == "healthy_answer"  # judge verdict, inline


def test_ingest_triggers_deep_eval_and_degrades_without_key() -> None:
    response = client.post("/v1/traces", json=make_trace_payload())
    assert response.status_code == 202

    trace_id = response.json()["trace_id"]
    deep = client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["deep"]

    assert len(deep) == 1
    assert deep[0]["label"] == "error"