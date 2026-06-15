from app.evaluators.context_relevance import evaluate_context_relevance
from app.schemas.traces import TraceIngestRequest


def make_trace(query: str, chunk_text: str) -> TraceIngestRequest:
    return TraceIngestRequest.model_validate(
        {
            "query": {
                "original": query,
            },
            "retrieval": {
                "chunks": [
                    {
                        "rank": 1,
                        "chunk_id": "chunk-1",
                        "text": chunk_text,
                    }
                ],
            },
            "generation": {
                "model": "gpt-4o-mini",
                "answer": "Placeholder answer.",
            },
        }
    )


def test_context_relevance_passes_when_query_terms_are_in_context() -> None:
    trace = make_trace(
        query="What is the refund policy?",
        chunk_text="The refund policy allows customers to request refunds within 30 days.",
    )

    result = evaluate_context_relevance(trace)

    assert result.evaluator_name == "context_relevance"
    assert result.label == "pass"
    assert result.score is not None
    assert result.score >= 0.7
    assert "refund" in result.details["matched_terms"]
    assert "policy" in result.details["matched_terms"]


def test_context_relevance_fails_when_context_is_unrelated() -> None:
    trace = make_trace(
        query="What is the refund policy?",
        chunk_text="Workspace regions include US and EU for enterprise accounts.",
    )

    result = evaluate_context_relevance(trace)

    assert result.label == "fail"
    assert result.score is not None
    assert result.score < 0.4
    assert "refund" in result.details["missing_terms"]


def test_context_relevance_uses_rewritten_query_when_available() -> None:
    trace = TraceIngestRequest.model_validate(
        {
            "query": {
                "original": "Can I get money back?",
                "rewritten": "What is the refund policy?",
            },
            "retrieval": {
                "chunks": [
                    {
                        "rank": 1,
                        "chunk_id": "chunk-1",
                        "text": "The refund policy allows refunds within 30 days.",
                    }
                ],
            },
            "generation": {
                "model": "gpt-4o-mini",
                "answer": "Refunds are available within 30 days.",
            },
        }
    )

    result = evaluate_context_relevance(trace)

    assert result.label == "pass"
    assert "refund" in result.details["matched_terms"]