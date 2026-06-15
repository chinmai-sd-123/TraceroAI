from app.evaluators.groundedness import evaluate_groundedness
from app.schemas.traces import TraceIngestRequest


def make_trace(answer: str, chunk_text: str) -> TraceIngestRequest:
    return TraceIngestRequest.model_validate(
        {
            "query": {
                "original": "What regions are supported?",
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
                "answer": answer,
            },
        }
    )


def test_groundedness_passes_when_answer_terms_are_in_context() -> None:
    trace = make_trace(
        answer="US and EU regions are supported.",
        chunk_text="The product supports US and EU regions for customers.",
    )

    result = evaluate_groundedness(trace)

    assert result.evaluator_name == "groundedness"
    assert result.label == "pass"
    assert result.score is not None
    assert result.score >= 0.75
    assert "region" in result.details["matched_terms"]
    assert "support" in result.details["matched_terms"]


def test_groundedness_fails_when_answer_terms_are_missing_from_context() -> None:
    trace = make_trace(
        answer="Phone support is available for enterprise customers.",
        chunk_text="The product supports email support for all paid plans.",
    )

    result = evaluate_groundedness(trace)

    assert result.label == "fail"
    assert result.score is not None
    assert result.score < 0.45
    assert "phone" in result.details["missing_terms"]


def test_groundedness_needs_review_for_empty_answer_terms() -> None:
    trace = make_trace(
        answer="OK.",
        chunk_text="The product supports US and EU regions.",
    )

    result = evaluate_groundedness(trace)

    assert result.label == "needs_review"
    assert result.score == 0