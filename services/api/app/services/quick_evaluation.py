from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.evaluators.context_relevance import evaluate_context_relevance
from app.evaluators.diagnosis import diagnose_trace, is_refusal
from app.evaluators.groundedness import evaluate_groundedness
from app.schemas.traces import NOT_DIAGNOSED, DiagnosisTrace, Trace, rag_generation
from app.services.embeddings import EmbeddingClient


NOT_DIAGNOSED_REASON = (
    "Not a RAG run: TraceroAI checks retrieval, grounding and a model answer, and this run "
    "has no single answer to check. Agent diagnosis is planned."
)


def run_quick_evaluation(
    trace: Trace,
    *,
    semantic: bool = True,
    embedder: EmbeddingClient | None = None,
) -> Trace:
    """Run the quick evaluators and diagnosis on a trace.

    The server is the source of truth for evaluations, so any quick
    evaluations or diagnosis sent by the client are overwritten.

    semantic=False is the lexical-only pass used on the ingest path: no network
    call, so ingest latency never depends on an embeddings provider. The
    background evaluation re-runs this with semantic=True.
    """
    # Embed query, context, and answer in ONE call and share the vectors with both
    # relevance evaluators — the query is embedded once instead of twice, and we
    # make one API round-trip per trace instead of two. If embeddings are
    # unavailable the evaluators fall back to lexical scoring on their own.
    if trace.generation is None:
        # Nothing to check: no model answer against retrieved context.
        trace.evaluations.quick = []
        trace.diagnosis = DiagnosisTrace(label=NOT_DIAGNOSED, reason=NOT_DIAGNOSED_REASON)
        return trace

    vectors = _embed_relevance_inputs(trace, embedder) if semantic else None

    quick_results = [
        evaluate_context_relevance(trace, embedder, vectors=vectors, semantic=semantic),
        evaluate_groundedness(trace),
        evaluate_answer_relevance(trace, embedder, vectors=vectors, semantic=semantic),
    ]

    trace.evaluations.quick = quick_results

    # A trace is a refusal if the model said so (answered=False) or the answer
    # text reads as a decline — diagnosed as correct_refusal, not a failure.
    refused = not trace.generation.answered or is_refusal(trace.generation.answer)
    # "embedding" only if a relevance check actually used embeddings; they fall
    # back to term overlap on their own when the embeddings call fails.
    used_embeddings = any(
        (result.evaluator_version or "").startswith("embedding") for result in quick_results
    )
    trace.diagnosis = diagnose_trace(
        quick_results, refused=refused, source="embedding" if used_embeddings else "lexical"
    )

    return trace


def _embed_relevance_inputs(
    trace: Trace,
    embedder: EmbeddingClient | None = None,
) -> dict[str, list[float]] | None:
    """Embed [query, context, answer] in one batched call.

    Returns a dict keyed by 'query'/'context'/'answer', or None if any input is
    empty or the embedding call fails — in which case the evaluators fall back to
    lexical scoring.
    """
    query = trace.query.rewritten or trace.query.original
    context = " ".join(chunk.text for chunk in trace.retrieval.chunks)
    answer = rag_generation(trace).answer

    if not (query.strip() and context.strip() and answer.strip()):
        return None

    try:
        client = embedder or EmbeddingClient()
        query_vec, context_vec, answer_vec = client.embed([query, context, answer])
    except Exception:
        return None

    return {"query": query_vec, "context": context_vec, "answer": answer_vec}
