"""Self-healing RAG recovery agent (optional extra: pip install traceroai[recovery]).

A LangGraph state machine that retries a RAG pipeline when TraceroAI's evaluation
diagnoses a failure: a retrieval miss re-retrieves with more/rewritten context, an
unsupported claim re-generates with a stricter grounding prompt, and after a bounded
number of attempts it gives up and marks the answer for human review. Every attempt
is sent to TraceroAI, so the dashboard shows the full retry chain.
"""

from __future__ import annotations
import time
from typing import Any, Callable, TypedDict

# langgraph/langchain are optional — only needed for recovery. Give a clear,
# actionable error instead of a cryptic ImportError if the extra isn't installed.
try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The recovery feature needs extra dependencies. "
        "Install them with:  pip install 'traceroai[recovery]'"
    ) from exc

from traceroai.client import TraceroClient


# The shape of the user's injected functions.
RetrieveFn = Callable[[str, int], list[dict[str, Any]]]  # (query, top_k) -> chunks
GenerateFn = Callable[[str, str], str]                    # (query, context) -> answer


class RecoveryState(TypedDict, total=False):
    """Working memory carried through the graph for one question."""
    question: str          # the original user question (never changes)
    query: str             # the current (possibly rewritten) retrieval query
    top_k: int             # current retrieval depth (raised on retrieval_miss)
    prompt_style: str      # "normal" | "strict" (strict on unsupported_claim)
    chunks: list[dict[str, Any]]
    prompt: str            # the prompt context the generator was given this attempt
    answer: str
    diagnosis: str         # the server's quick-eval diagnosis for the last attempt
    attempt: int           # how many attempts so far
    trace_ids: list[str]   # the trace id of every attempt (the retry chain)
    retrieval_ms: int      # timing of the last retrieve step
    generation_ms: int     # timing of the last generate step

def _format_context(chunks: list[dict[str, Any]]) -> str:
    """Join retrieved chunks into a single context string with [n] citations."""
    return "\n\n".join(
        f"[{i + 1}] {c.get('text', '')}" for i, c in enumerate(chunks)
    )


def _make_nodes(
    client: TraceroClient,
    retrieve: RetrieveFn,
    generate: GenerateFn,
    project_id: str,
):
    """Build the graph's node functions, closing over the user's retrieve/generate
    and the TraceroAI client. Returns (retrieve_node, generate_node, evaluate_node)."""

    def retrieve_node(state: RecoveryState) -> dict[str, Any]:
        query = state.get("query") or state["question"]
        top_k = state.get("top_k", 3)
        start = time.perf_counter()
        chunks = retrieve(query, top_k)
        return {"chunks": chunks, "retrieval_ms": int((time.perf_counter() - start) * 1000)}

    def generate_node(state: RecoveryState) -> dict[str, Any]:
        query = state.get("query") or state["question"]
        context = _format_context(state.get("chunks", []))
        # On a grounding failure we re-enter with prompt_style="strict": prepend a
        # hard instruction so generate() can choose to be more conservative.
        if state.get("prompt_style") == "strict":
            query = (
                f"{query}\n\n(Answer ONLY from the provided context. "
                f"If it is not enough, say you don't know.)"
            )
        # Record the prompt the generator saw this attempt (context + question).
        prompt = f"Context:\n{context}\n\nQuestion: {query}"
        start = time.perf_counter()
        answer = generate(query, context)
        return {
            "answer": answer,
            "prompt": prompt,
            "generation_ms": int((time.perf_counter() - start) * 1000),
        }

    def evaluate_node(state: RecoveryState) -> dict[str, Any]:
        # Send the attempt as a trace; the server runs quick eval synchronously,
        # so the diagnosis is ready when we read it back. This is the eval that
        # drives recovery routing.
        retrieval_ms = state.get("retrieval_ms", 0)
        generation_ms = state.get("generation_ms", 0)
        trace_kwargs: dict[str, Any] = {
            "query": {"original": state["question"]},
            "retrieval": {"strategy": "recovery", "chunks": state.get("chunks", [])},
            "generation": {"model": "recovery-agent", "answer": state.get("answer", "")},
            "latency": {
                "retrieval_ms": retrieval_ms,
                "generation_ms": generation_ms,
                "total_ms": retrieval_ms + generation_ms,
            },
            "metadata": {"attempt": state.get("attempt", 0) + 1, "agent": "recovery"},
            "project": {"project_id": project_id},
        }
        if state.get("prompt"):
            trace_kwargs["prompt"] = {"content": state["prompt"], "version": "recovery_v1"}
        trace_id = client.log_trace(**trace_kwargs)
        diagnosis = "needs_review"
        try:
            trace = client.get_trace(trace_id)
            diagnosis = trace.get("diagnosis", {}).get("label", "needs_review")
        except Exception:
            pass  # if the read fails, treat as needs_review (fail-safe)

        return {
            "diagnosis": diagnosis,
            "attempt": state.get("attempt", 0) + 1,
            "trace_ids": state.get("trace_ids", []) + [str(trace_id)],
        }

    return retrieve_node, generate_node, evaluate_node



# Diagnoses that mean "good — stop and return success".
_SUCCESS = {"healthy_answer", "correct_refusal"}


def _route(state: RecoveryState, max_attempts: int) -> str:
    """Conditional edge: decide the next node from the diagnosis. THIS is the
    recovery logic — it maps a failure to the stage that should be retried."""
    diagnosis = state.get("diagnosis", "needs_review")
    attempt = state.get("attempt", 0)

    if diagnosis in _SUCCESS:
        return "success"            # -> END
    if attempt >= max_attempts:
        return "give_up"            # -> END (bounded: no infinite loops)
    if diagnosis == "retrieval_miss":
        return "fix_retrieval"      # -> retrieve again, with more/rewritten context
    if diagnosis == "unsupported_claim":
        return "fix_generation"     # -> generate again, stricter grounding
    # wrong_answer / needs_review / anything else: try re-retrieving once more.
    return "fix_retrieval"


# State updates applied when we take a recovery branch (the "levers").
def _bump_retrieval(state: RecoveryState) -> dict[str, Any]:
    return {
        "top_k": state.get("top_k", 3) + 2,                 # retrieve more
        "query": f"{state['question']} (be specific and complete)",  # rewrite
    }


def _tighten_generation(state: RecoveryState) -> dict[str, Any]:
    return {"prompt_style": "strict"}


class RecoveryResult(TypedDict):
    answer: str
    diagnosis: str
    attempts: int
    succeeded: bool
    trace_ids: list[str]
    deep_eval: list[dict[str, Any]] | None


class RecoveryAgent:
    """A self-healing RAG agent. You supply retrieve()/generate(); the agent runs
    them, evaluates each attempt via TraceroAI, and retries the stage that failed
    until the answer is healthy or max_attempts is reached.

        agent = RecoveryAgent(client, retrieve=my_retrieve, generate=my_generate)
        result = agent.run("How long does a refund take?")
    """

    def __init__(
        self,
        client: TraceroClient,
        *,
        retrieve: RetrieveFn,
        generate: GenerateFn,
        max_attempts: int = 3,
        project_id: str = "recovery-agent",
    ) -> None:
        self.client = client
        self._max_attempts = max_attempts
        retrieve_node, generate_node, evaluate_node = _make_nodes(
            client, retrieve, generate, project_id
        )
        self._graph = self._build_graph(retrieve_node, generate_node, evaluate_node)

    def _build_graph(self, retrieve_node, generate_node, evaluate_node):
        g = StateGraph(RecoveryState)
        g.add_node("retrieve", retrieve_node)
        g.add_node("generate", generate_node)
        g.add_node("evaluate", evaluate_node)
        # tiny nodes that apply the recovery levers before looping back
        g.add_node("bump_retrieval", _bump_retrieval)
        g.add_node("tighten_generation", _tighten_generation)

        g.add_edge(START, "retrieve")
        g.add_edge("retrieve", "generate")
        g.add_edge("generate", "evaluate")

        # the conditional edge: route from evaluate based on the diagnosis
        g.add_conditional_edges(
            "evaluate",
            lambda s: _route(s, self._max_attempts),
            {
                "success": END,
                "give_up": END,
                "fix_retrieval": "bump_retrieval",
                "fix_generation": "tighten_generation",
            },
        )
        # after applying a lever, loop back to the right stage
        g.add_edge("bump_retrieval", "retrieve")
        g.add_edge("tighten_generation", "generate")
        return g.compile()

    def _poll_deep_verdict(
        self, client: TraceroClient, trace_id: str,
        *, attempts: int = 5, interval: float = 1.5,
    ) -> dict[str, Any] | None:
        """Poll the trace until the async deep (LLM-judge) eval lands.

        Returns the deep evaluations list, or None if it doesn't arrive in time
        (fail-open: the caller keeps the quick verdict and notes 'deep pending').
        """
        for _ in range(attempts):
            try:
                trace = client.get_trace(trace_id)
            except Exception:
                return None
            deep = trace.get("evaluations", {}).get("deep") or []
            if deep:
                return deep
            time.sleep(interval)
        return None


    def run(
        self,
        question: str,
        *,
        confirm_with_deep_eval: bool = True,
        deep_eval_interval: float = 1.5,
    ) -> RecoveryResult:
        final = self._graph.invoke(
            {"question": question, "query": question, "top_k": 3, "attempt": 0},
            {"recursion_limit": self._max_attempts * 4 + 5},
        )
        trace_ids = final.get("trace_ids", [])

        deep_verdict = None
        if confirm_with_deep_eval and trace_ids:
            # Confirm the FINAL answer with the LLM judge (runs async server-side).
            deep_verdict = self._poll_deep_verdict(
                self.client, trace_ids[-1], interval=deep_eval_interval
            )

        return RecoveryResult(
            answer=final.get("answer", ""),
            diagnosis=final.get("diagnosis", "needs_review"),
            attempts=final.get("attempt", 0),
            succeeded=final.get("diagnosis", "") in _SUCCESS,
            trace_ids=trace_ids,
            deep_eval=deep_verdict,          # list of deep results, or None if pending
        )
