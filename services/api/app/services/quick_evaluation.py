from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.evaluators.context_relevance import evaluate_context_relevance
from app.evaluators.diagnosis import diagnose_trace
from app.evaluators.groundedness import evaluate_groundedness
from app.schemas.traces import TraceIngestRequest


def run_quick_evaluation(trace: TraceIngestRequest) -> TraceIngestRequest:
    """Run the deterministic quick evaluators and diagnosis on a trace.

    The server is the source of truth for evaluations, so any quick
    evaluations or diagnosis sent by the client are overwritten.
    """
    quick_results = [
        evaluate_context_relevance(trace),
        evaluate_groundedness(trace),
        evaluate_answer_relevance(trace),
    ]

    trace.evaluations.quick = quick_results
    trace.diagnosis = diagnose_trace(quick_results)

    return trace
