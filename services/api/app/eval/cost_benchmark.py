"""Per-trace cost benchmark — measures what one trace actually costs to evaluate.

Run:
    .venv/Scripts/python.exe -m app.eval.cost_benchmark

Generation cost is already computed + stored per trace by the ingest path. The
EVAL cost (embeddings for quick eval + LLM judge for deep eval) is not tracked in
production, so this script measures it directly: it runs the real quick + deep
evaluation over the golden set, captures actual token usage from each provider
call, and prices it via the same app.services.cost table the server uses.

Output is the average per-trace cost broken down by stage — a real, citable
number. Token usage is captured from live API responses, not estimated. Prints a
clear NOTE and exits cleanly if no judge/embedding key is configured (never
fabricates a cost).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.eval.regression_gate import load_golden_cases
from app.evaluators.answer_relevance import evaluate_answer_relevance
from app.evaluators.context_relevance import evaluate_context_relevance
from app.evaluators.deep_groundedness import evaluate_deep_groundedness
from app.evaluators.deep_relevance import (
    evaluate_deep_answer_relevance,
    evaluate_deep_context_relevance,
)
from app.evaluators.groundedness import evaluate_groundedness
from app.schemas.traces import TraceIngestRequest
from app.services.cost import price_for, refresh_litellm_prices
from app.services.embeddings import EmbeddingClient
from app.services.llm_judge import OpenAIJudge
from app.services.quick_evaluation import _embed_relevance_inputs


@dataclass
class Meter:
    """Accumulates token usage and the resulting USD cost, per model."""

    embed_prompt_tokens: int = 0
    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0
    embed_calls: int = 0
    judge_calls: int = 0
    _notes: list[str] = field(default_factory=list)

    def cost_for(self, model: str, prompt: int, completion: int) -> float | None:
        price = price_for(model)
        if price is None:
            self._notes.append(f"no price for {model!r}")
            return None
        in_price, out_price = price
        return (prompt / 1000) * in_price + (completion / 1000) * out_price


class MeteredEmbeddingClient(EmbeddingClient):
    """EmbeddingClient that records token usage from each embeddings call."""

    def __init__(self, meter: Meter, settings=None) -> None:
        super().__init__(settings)
        self._meter = meter

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self._settings.embedding_model, input=texts
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._meter.embed_prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self._meter.embed_calls += 1
        return [item.embedding for item in response.data]


class MeteredJudge(OpenAIJudge):
    """OpenAIJudge that records token usage by patching the shared client.

    The judge's methods call self._client.chat.completions.parse and discard
    `.usage`. Rather than override every method, we wrap the parse call once so
    every judge method is metered uniformly.
    """

    def __init__(self, meter: Meter) -> None:
        super().__init__()
        self._meter = meter
        original_parse = self._client.chat.completions.parse

        def metered_parse(*args, **kwargs):
            completion = original_parse(*args, **kwargs)
            usage = getattr(completion, "usage", None)
            if usage is not None:
                self._meter.judge_prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self._meter.judge_completion_tokens += (
                    getattr(usage, "completion_tokens", 0) or 0
                )
            self._meter.judge_calls += 1
            return completion

        # Patch this instance's client only (not the class) — isolated to the benchmark.
        self._client.chat.completions.parse = metered_parse  # type: ignore[assignment]


DEEP_EVALUATORS = (
    evaluate_deep_context_relevance,
    evaluate_deep_groundedness,
    evaluate_deep_answer_relevance,
)


def main() -> None:
    settings = get_settings()
    # Standalone script: no API startup hook, so load live prices here (falls back
    # to the built-in table if the fetch fails).
    refresh_litellm_prices()
    if not settings.openai_api_key:
        print(
            "Cost benchmark SKIPPED — no key configured (TRACEROAI_OPENAI_API_KEY). "
            "Not reporting a fabricated cost."
        )
        return

    cases = load_golden_cases()
    n = len(cases)
    meter = Meter()

    embedder = MeteredEmbeddingClient(meter)
    judge = MeteredJudge(meter)

    print("=" * 70)
    print(f"TraceroAI per-trace EVAL cost benchmark — {n} golden cases")
    print(f"embedding_model={settings.embedding_model!r}  judge_model={settings.judge_model!r}")
    print("=" * 70)

    try:
        for case in cases:
            trace = TraceIngestRequest(**case["trace"])
            # Quick eval — mirror run_quick_evaluation, but feed the metered embedder
            # into the (one) batched embedding call so its token usage is captured.
            vectors = _embed_relevance_inputs(trace, embedder=embedder)
            evaluate_context_relevance(trace, vectors=vectors)
            evaluate_groundedness(trace)
            evaluate_answer_relevance(trace, vectors=vectors)
            # Deep eval (judge) — run the three judge evaluators with the metered judge.
            for evaluator in DEEP_EVALUATORS:
                evaluator(trace, judge)
    except Exception as exc:
        print(f"\nCost benchmark FAILED while calling the provider: {exc}")
        print("(bad key / wrong endpoint) — not reporting a partial cost.")
        return

    embed_cost = meter.cost_for(
        settings.embedding_model, meter.embed_prompt_tokens, 0
    ) or 0.0
    judge_cost = meter.cost_for(
        settings.judge_model, meter.judge_prompt_tokens, meter.judge_completion_tokens
    ) or 0.0
    total_eval_cost = embed_cost + judge_cost

    print(f"\nTotals across {n} traces:")
    print(
        f"  embeddings : {meter.embed_calls} calls, "
        f"{meter.embed_prompt_tokens} tokens  ->  ${embed_cost:.6f}"
    )
    print(
        f"  judge      : {meter.judge_calls} calls, "
        f"{meter.judge_prompt_tokens} in + {meter.judge_completion_tokens} out tokens  "
        f"->  ${judge_cost:.6f}"
    )
    print(f"  total eval : ${total_eval_cost:.6f}")

    print(f"\nPer-trace EVAL cost (avg over {n} traces):")
    print(f"  quick eval (embeddings): ${embed_cost / n:.6f}")
    print(f"  deep eval  (LLM judge) : ${judge_cost / n:.6f}")
    print(f"  TOTAL eval / trace     : ${total_eval_cost / n:.6f}")
    print(
        "\nNOTE: generation (answer-LLM) cost is tracked separately per trace by the "
        "ingest path; this benchmark measures only the eval overhead the platform adds."
    )
    if meter._notes:
        print("WARN:", "; ".join(sorted(set(meter._notes))))
    print()


if __name__ == "__main__":
    main()
