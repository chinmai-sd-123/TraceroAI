"""Answer relevance: does the generated answer actually address the query?

Primary path: semantic similarity via a hosted embedding model. Fallback path:
deterministic term overlap — used when embeddings are unavailable or fail, so
ingest never breaks (fail-open).
"""

from app.evaluators.groundedness import extract_terms
from app.schemas.traces import EvaluationResult, TraceIngestRequest
from app.services.embeddings import EmbeddingClient, cosine_similarity

EVALUATOR_NAME = "answer_relevance"
EVALUATOR_VERSION_EMBEDDING = "embedding_v1"
EVALUATOR_VERSION_LEXICAL = "deterministic_v1"

PASS_THRESHOLD = 0.65
REVIEW_THRESHOLD = 0.50


def evaluate_answer_relevance(
    trace: TraceIngestRequest,
    embedder: EmbeddingClient | None = None,
    vectors: dict[str, list[float]] | None = None,
) -> EvaluationResult:
    query = trace.query.rewritten or trace.query.original
    answer = trace.generation.answer

    result = _embedding_relevance(query, answer, embedder, vectors)
    if result is not None:
        return result
    return _lexical_relevance(query, answer)


def _embedding_relevance(
    query: str,
    answer: str,
    embedder: EmbeddingClient | None,
    vectors: dict[str, list[float]] | None = None,
) -> EvaluationResult | None:
    if not query.strip() or not answer.strip():
        return None

    # Prefer precomputed vectors (batched once by the orchestrator).
    if vectors and "query" in vectors and "answer" in vectors:
        query_vec, answer_vec = vectors["query"], vectors["answer"]
    else:
        try:
            client = embedder or EmbeddingClient()
            query_vec, answer_vec = client.embed([query, answer])
        except Exception:
            return None

    score = cosine_similarity(query_vec, answer_vec)
    if score >= PASS_THRESHOLD:
        label = "pass"
    elif score >= REVIEW_THRESHOLD:
        label = "needs_review"
    else:
        label = "fail"

    return EvaluationResult(
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION_EMBEDDING,
        label=label,
        score=round(score, 3),
        reason=(
            f"Semantic similarity between the query and answer is "
            f"{score:.2f} (cosine). Threshold for pass is {PASS_THRESHOLD:.2f}."
        ),
        details={"method": "embedding_cosine"},
    )


def _lexical_relevance(query: str, answer: str) -> EvaluationResult:
    query_terms = extract_terms(query)
    answer_terms = extract_terms(answer)

    if not query_terms:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION_LEXICAL,
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
        evaluator_version=EVALUATOR_VERSION_LEXICAL,
        label=label,
        score=round(score, 3),
        reason=(
            f"Term overlap between the query and answer is {score:.2f} "
            f"(matched: {', '.join(matched_terms[:5]) or 'none'})."
        ),
        details={
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "query_term_count": len(query_terms),
            "answer_term_count": len(answer_terms),
        },
    )
