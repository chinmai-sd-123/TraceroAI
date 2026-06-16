from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.evaluators.context_relevance import evaluate_context_relevance
from app.evaluators.diagnosis import diagnose_trace, is_refusal
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

    # A trace is a refusal if the model said so (answered=False) or the answer
    # text reads as a decline — diagnosed as correct_refusal, not a failure.
    refused = not trace.generation.answered or is_refusal(trace.generation.answer)
    trace.diagnosis = diagnose_trace(quick_results, refused=refused)

    return trace
