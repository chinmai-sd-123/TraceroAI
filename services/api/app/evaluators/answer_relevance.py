from app.evaluators.groundedness import extract_terms
from app.schemas.traces import EvaluationResult, TraceIngestRequest


EVALUATOR_NAME = "answer_relevance"
EVALUATOR_VERSION = "deterministic_v1"


def evaluate_answer_relevance(trace: TraceIngestRequest) -> EvaluationResult:
    query_terms = extract_terms(trace.query.rewritten or trace.query.original)
    answer_terms = extract_terms(trace.generation.answer)

    if not query_terms:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION,
            label="needs_review",
            score=0,
            reason="The query does not contain enough meaningful terms to evaluate answer relevance.",
            details={"matched_terms": [], "missing_terms": []},
        )

    matched_terms = sorted(query_terms.intersection(answer_terms))
    missing_terms = sorted(query_terms.difference(answer_terms))
    score = len(matched_terms) / len(query_terms)

    if score >= 0.7:
        label = "pass"
    elif score >= 0.4:
        label = "needs_review"
    else:
        label = "fail"

    return EvaluationResult(
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        label=label,
        score=round(score, 3),
        reason=build_reason(label, score, matched_terms, missing_terms),
        details={
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "query_term_count": len(query_terms),
            "answer_term_count": len(answer_terms),
        },
    )


def build_reason(
    label: str,
    score: float,
    matched_terms: list[str],
    missing_terms: list[str],
) -> str:
    matched_preview = ", ".join(matched_terms[:5]) or "none"
    missing_preview = ", ".join(missing_terms[:5]) or "none"

    if label == "pass":
        return (
            f"The answer directly addresses the query "
            f"(score={score:.2f}). Matched: {matched_preview}."
        )

    if label == "needs_review":
        return (
            f"The answer partially addresses the query "
            f"(score={score:.2f}). Missing: {missing_preview}."
        )

    return (
        f"The answer has low overlap with the query "
        f"(score={score:.2f}). Missing: {missing_preview}."
    )