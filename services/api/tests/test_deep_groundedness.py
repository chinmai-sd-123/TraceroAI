from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.services.deep_evaluation import run_deep_evaluation
from app.services.llm_judge import ClaimGroundednessVerdict, JudgedClaim

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


def test_deep_evaluation_populates_grounded_result() -> None:
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]

    run_deep_evaluation(UUID(trace_id), judge=StubJudge())

    trace = client.get(f"/v1/traces/{trace_id}").json()
    deep = trace["evaluations"]["deep"]

    assert len(deep) == 1
    assert deep[0]["evaluator_name"] == "claim_groundedness"
    assert deep[0]["label"] == "grounded"
    assert deep[0]["details"]["claims"][0]["supported"] is True


def test_ingest_triggers_deep_eval_and_degrades_without_key() -> None:
    response = client.post("/v1/traces", json=make_trace_payload())
    assert response.status_code == 202

    trace_id = response.json()["trace_id"]
    deep = client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["deep"]

    assert len(deep) == 1
    assert deep[0]["label"] == "error"
