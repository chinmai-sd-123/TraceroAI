from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.schemas.traces import TraceIngestRequest


def make_trace(query: str, answer: str) -> TraceIngestRequest:
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
                        "text": "Placeholder context.",
                    }
                ],
            },
            "generation": {
                "model": "gpt-4o-mini",
                "answer": answer,
            },
        }
    )


def test_answer_relevance_passes_when_answer_addresses_query() -> None:
    trace = make_trace(
        query="What is the refund policy?",
        answer="The refund policy allows refunds within 30 days.",
    )

    result = evaluate_answer_relevance(trace)

    assert result.evaluator_name == "answer_relevance"
    assert result.label == "pass"
    assert result.score is not None
    assert result.score >= 0.7
    assert "refund" in result.details["matched_terms"]
    assert "policy" in result.details["matched_terms"]


def test_answer_relevance_fails_when_answer_is_unrelated() -> None:
    trace = make_trace(
        query="What is the refund policy?",
        answer="The product supports US and EU regions.",
    )

    result = evaluate_answer_relevance(trace)

    assert result.label == "fail"
    assert result.score is not None
    assert result.score < 0.4
    assert "refund" in result.details["missing_terms"]


def test_answer_relevance_uses_rewritten_query_when_available() -> None:
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
                        "text": "Placeholder context.",
                    }
                ],
            },
            "generation": {
                "model": "gpt-4o-mini",
                "answer": "The refund policy allows refunds within 30 days.",
            },
        }
    )

    result = evaluate_answer_relevance(trace)

    assert result.label == "pass"
    assert "refund" in result.details["matched_terms"]