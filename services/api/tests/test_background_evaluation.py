from uuid import UUID

from fastapi.testclient import TestClient

import app.api.routes.traces as traces_route
from app.core.config import get_settings
from app.main import app
from app.services import embeddings
from app.services.deep_evaluation import run_deep_evaluation
from tests.test_deep_groundedness import StubJudge, make_trace_payload

client = TestClient(app)


class StubEmbedder:
    """Identical vectors for every text -> cosine 1.0 -> relevance passes."""

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]


def _quick_versions(trace_id: str) -> dict[str, str]:
    quick = client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["quick"]
    return {result["evaluator_name"]: result["evaluator_version"] for result in quick}


def test_ingest_never_calls_embeddings_even_with_a_key(monkeypatch) -> None:
    # A configured key used to mean an embeddings round-trip inside POST /v1/traces.
    monkeypatch.setattr(get_settings(), "openai_api_key", "sk-test")
    # Keep the post-response background pass out of this test (it would call out).
    monkeypatch.setattr(traces_route, "run_deep_evaluation", lambda *args, **kwargs: None)

    calls: list[list[str]] = []

    def _record(self, texts):
        calls.append(texts)
        raise AssertionError("ingest must not embed")

    monkeypatch.setattr(embeddings.EmbeddingClient, "embed", _record)

    response = client.post("/v1/traces", json=make_trace_payload())

    assert response.status_code == 202
    assert calls == []
    versions = _quick_versions(response.json()["trace_id"])
    assert versions["context_relevance"] == "deterministic_v1"
    assert versions["answer_relevance"] == "deterministic_v1"


def test_background_pass_upgrades_quick_eval_and_applies_judge() -> None:
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]
    embedder = StubEmbedder()

    run_deep_evaluation(UUID(trace_id), judge=StubJudge(), embedder=embedder)

    assert embedder.calls == 1  # query, context and answer embedded in one batch
    versions = _quick_versions(trace_id)
    assert versions["context_relevance"] == "embedding_v1"
    assert versions["answer_relevance"] == "embedding_v1"

    trace = client.get(f"/v1/traces/{trace_id}").json()
    assert {r["evaluator_name"] for r in trace["evaluations"]["deep"]} == {
        "deep_context_relevance",
        "claim_groundedness",
        "deep_answer_relevance",
    }
    assert trace["diagnosis"]["label"] == "healthy_answer"


def test_background_pass_without_judge_keeps_semantic_quick_diagnosis(monkeypatch) -> None:
    trace_id = client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]
    deep_before = client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["deep"]
    monkeypatch.setattr(get_settings(), "deep_eval_enabled", False)

    run_deep_evaluation(UUID(trace_id), embedder=StubEmbedder())

    trace = client.get(f"/v1/traces/{trace_id}").json()
    assert _quick_versions(trace_id)["context_relevance"] == "embedding_v1"
    assert trace["evaluations"]["deep"] == deep_before  # untouched, not cleared
    # Diagnosis now comes from the semantic quick pass (both relevance checks pass).
    assert trace["diagnosis"]["label"] != "pending"
