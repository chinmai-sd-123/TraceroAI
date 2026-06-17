"""Embedding-path tests for context/answer relevance.

The evaluators take an optional `embedder` (dependency injection), so we pass a
stub that returns canned vectors — no network, fully deterministic. The stub maps
each input string to a chosen vector, letting us control the cosine similarity and
therefore the label.
"""

from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.evaluators.context_relevance import evaluate_context_relevance
from app.schemas.traces import TraceIngestRequest


class StubEmbedder:
    """Returns a preset vector per input text; unknown text -> orthogonal vector."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vectors.get(t, [0.0, 1.0]) for t in texts]


def make_trace(query: str, chunk_text: str, answer: str) -> TraceIngestRequest:
    return TraceIngestRequest.model_validate(
        {
            "query": {"original": query},
            "retrieval": {"chunks": [{"rank": 1, "chunk_id": "c1", "text": chunk_text}]},
            "generation": {"model": "gpt-4o-mini", "answer": answer},
        }
    )


def test_context_relevance_passes_on_high_cosine() -> None:
    query, context = "How long does a refund take?", "Refunds take 5-7 business days."
    # Identical vectors -> cosine 1.0 -> well above PASS_THRESHOLD (0.65).
    embedder = StubEmbedder({query: [1.0, 0.0], context: [1.0, 0.0]})

    result = evaluate_context_relevance(make_trace(query, context, "irrelevant"), embedder)

    assert result.evaluator_version == "embedding_v1"
    assert result.label == "pass"
    assert result.score >= 0.65


def test_context_relevance_fails_on_low_cosine() -> None:
    query, context = "How long does a refund take?", "Cats are mammals."
    # Orthogonal vectors -> cosine 0.0 -> below REVIEW_THRESHOLD (0.50) -> fail.
    embedder = StubEmbedder({query: [1.0, 0.0], context: [0.0, 1.0]})

    result = evaluate_context_relevance(make_trace(query, context, "irrelevant"), embedder)

    assert result.evaluator_version == "embedding_v1"
    assert result.label == "fail"


def test_answer_relevance_uses_embedding_path() -> None:
    query, answer = "How long does a refund take?", "Refunds take 5-7 business days."
    embedder = StubEmbedder({query: [1.0, 0.0], answer: [1.0, 0.0]})

    result = evaluate_answer_relevance(make_trace(query, "ctx", answer), embedder)

    assert result.evaluator_version == "embedding_v1"
    assert result.label == "pass"


def test_falls_back_to_lexical_when_embedder_raises() -> None:
    class BrokenEmbedder:
        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("embedding API down")

    query = "What is the refund policy?"
    context = "The refund policy allows refunds within 30 days."

    result = evaluate_context_relevance(make_trace(query, context, "ans"), BrokenEmbedder())

    # The embedding path raised -> we fell back to the deterministic scorer.
    assert result.evaluator_version == "deterministic_v1"
    assert "matched_terms" in result.details
