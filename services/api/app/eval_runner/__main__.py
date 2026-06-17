"""CLI for the RAG experiment harness.

Runs a labeled dataset across pipeline variants, grades each answer with the LLM
judge, picks a winner, and POSTs the result to the eval-runs API (or prints it).

Usage:
    python -m app.eval_runner --dataset support_faq_v1 --post
    python -m app.eval_runner --api-url https://traceroai.onrender.com --post
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

from app.eval_runner.datasets import get_dataset
from app.eval_runner.rag import VariantConfig
from app.eval_runner.runner import run_experiment

# The variants we compare. The interesting hypothesis: does the stricter "v2"
# prompt (which refuses when unsupported) beat the lax "v1" on the dataset's
# out-of-knowledge cases? And does more retrieved context (top_k) help?
DEFAULT_VARIANTS = [
    VariantConfig(variant_id="v1_lax_k3", name="Lax prompt, top_k=3", top_k=3, prompt_variant="v1"),
    VariantConfig(variant_id="v2_strict_k3", name="Strict prompt, top_k=3", top_k=3, prompt_variant="v2"),
    VariantConfig(variant_id="v2_strict_k5", name="Strict prompt, top_k=5", top_k=5, prompt_variant="v2"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a RAG experiment eval run.")
    parser.add_argument("--dataset", default="support_faq_v1", help="dataset id")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="eval-runs API base")
    parser.add_argument("--post", action="store_true", help="POST the result to the API")
    parser.add_argument("--project", default="experiments", help="project id to tag the run")
    args = parser.parse_args()

    try:
        dataset = get_dataset(args.dataset)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Running experiment on '{dataset.name}' "
          f"({len(dataset.cases)} cases x {len(DEFAULT_VARIANTS)} variants)...")

    run = run_experiment(dataset, DEFAULT_VARIANTS, project_id=args.project)

    print("\n=== Variant results ===")
    for v in run.variants:
        acc = next((m.score for m in v.metrics if m.metric_name == "accuracy"), None)
        ungradeable = v.config.get("ungradeable_cases", 0)
        note = f"  [!] {ungradeable} ungradeable (grader errored)" if ungradeable else ""
        print(f"  {v.name:28} accuracy={acc}  ({v.passed_cases}/{v.passed_cases + v.failed_cases} graded)"
              f"  avg_latency={v.average_latency_ms}ms{note}")
    print(f"\n>>> {run.summary.recommendation}")

    if args.post:
        url = f"{args.api_url.rstrip('/')}/v1/eval-runs"
        payload = json.loads(run.model_dump_json())
        try:
            resp = httpx.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            print(f"\nPosted to {url} -> {resp.status_code} "
                  f"(eval_run_id={resp.json().get('eval_run_id')})")
        except Exception as exc:
            print(f"\nPOST failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
