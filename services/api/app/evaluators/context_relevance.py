"""Context relevance: does the retrieved context actually relate to the query?

Primary path: semantic similarity via a hosted embedding model (catches paraphrase
the way real RAG-eval tools do). Fallback path: deterministic term overlap — used
when no embedding provider is configured or the embedding call fails, so ingest
never breaks (fail-open).
"""

from app.evaluators.groundedness import extract_terms
from app.schemas.traces import EvaluationResult, TraceIngestRequest
from app.services.embeddings import EmbeddingClient, cosine_similarity

EVALUATOR_NAME = "context_relevance"
EVALUATOR_VERSION_EMBEDDING = "embedding_v1"
EVALUATOR_VERSION_LEXICAL = "deterministic_v1"

# Cosine thresholds, calibrated for text-embedding-3-small: relevant query/context
# pairs score ~0.55-0.72, clearly-irrelevant pairs ~0.05-0.10 — a wide, clean gap.
# Pass at 0.45 (above noise, below the lowest relevant), review down to 0.30.
PASS_THRESHOLD = 0.45
REVIEW_THRESHOLD = 0.30


def evaluate_context_relevance(
    trace: TraceIngestRequest,
    embedder: EmbeddingClient | None = None,
    vectors: dict[str, list[float]] | None = None,
) -> EvaluationResult:
    query = trace.query.rewritten or trace.query.original
    context = " ".join(chunk.text for chunk in trace.retrieval.chunks)

    result = _embedding_relevance(query, context, embedder, vectors)
    if result is not None:
        return result
    return _lexical_relevance(query, context)



def _embedding_relevance(
    query: str,
    context: str,
    embedder: EmbeddingClient | None,
    vectors: dict[str, list[float]] | None= None,
) -> EvaluationResult | None:
    """Semantic path. Returns None if embeddings are unavailable, so the caller
    falls back to the lexical scorer."""
    if not query.strip() or not context.strip():
        return None

    # Prefer precomputed vectors (batched once by the orchestrator). Only embed
    # here if they weren't supplied — keeps standalone use working.
    if vectors and "query" in vectors and "context" in vectors:
        query_vec, context_vec = vectors["query"], vectors["context"]
    else:
        try:
            client = embedder or EmbeddingClient()
            query_vec, context_vec = client.embed([query, context])
        except Exception:
            return None

    score = cosine_similarity(query_vec, context_vec)
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
            f"Semantic similarity between the query and retrieved context is "
            f"{score:.2f} (cosine). Threshold for pass is {PASS_THRESHOLD:.2f}."
        ),
        details={"method": "embedding_cosine"},
    )


def _lexical_relevance(query: str, context: str) -> EvaluationResult:
    """Fallback: deterministic term overlap (the original behavior)."""
    query_terms = extract_terms(query)
    context_terms = extract_terms(context)

    if not query_terms:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION_LEXICAL,
            label="needs_review",
            score=0,
            reason="The query does not contain enough meaningful terms to evaluate retrieval relevance.",
            details={"matched_terms": [], "missing_terms": []},
        )

    matched_terms = sorted(query_terms.intersection(context_terms))
    missing_terms = sorted(query_terms.difference(context_terms))
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
            f"Term overlap between the query and context is {score:.2f} "
            f"(matched: {', '.join(matched_terms[:5]) or 'none'})."
        ),
        details={
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "query_term_count": len(query_terms),
            "context_term_count": len(context_terms),
        },
    )
