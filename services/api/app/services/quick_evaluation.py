from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.evaluators.context_relevance import evaluate_context_relevance
from app.evaluators.diagnosis import diagnose_trace, is_refusal
from app.evaluators.groundedness import evaluate_groundedness
from app.schemas.traces import TraceIngestRequest
from app.services.embeddings import EmbeddingClient


def run_quick_evaluation(trace: TraceIngestRequest) -> TraceIngestRequest:
    """Run the deterministic quick evaluators and diagnosis on a trace.

    The server is the source of truth for evaluations, so any quick
    evaluations or diagnosis sent by the client are overwritten.
    """
    # Embed query, context, and answer in ONE call and share the vectors with both
    # relevance evaluators — the query is embedded once instead of twice, and we
    # make one API round-trip per trace instead of two. If embeddings are
    # unavailable the evaluators fall back to lexical scoring on their own.
    vectors = _embed_relevance_inputs(trace)

    quick_results = [
        evaluate_context_relevance(trace, vectors=vectors),
        evaluate_groundedness(trace),
        evaluate_answer_relevance(trace, vectors=vectors),
    ]

    trace.evaluations.quick = quick_results

    # A trace is a refusal if the model said so (answered=False) or the answer
    # text reads as a decline — diagnosed as correct_refusal, not a failure.
    refused = not trace.generation.answered or is_refusal(trace.generation.answer)
    trace.diagnosis = diagnose_trace(quick_results, refused=refused)

    return trace


def _embed_relevance_inputs(
    trace: TraceIngestRequest,
    embedder: EmbeddingClient | None = None,
) -> dict[str, list[float]] | None:
    """Embed [query, context, answer] in one batched call.

    Returns a dict keyed by 'query'/'context'/'answer', or None if any input is
    empty or the embedding call fails — in which case the evaluators fall back to
    lexical scoring.
    """
    query = trace.query.rewritten or trace.query.original
    context = " ".join(chunk.text for chunk in trace.retrieval.chunks)
    answer = trace.generation.answer

    if not (query.strip() and context.strip() and answer.strip()):
        return None

    try:
        client = embedder or EmbeddingClient()
        query_vec, context_vec, answer_vec = client.embed([query, context, answer])
    except Exception:
        return None

    return {"query": query_vec, "context": context_vec, "answer": answer_vec}
