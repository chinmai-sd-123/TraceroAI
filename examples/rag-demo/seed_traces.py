"""Seed TraceroAI with a diverse set of demo traces.

Runs the demo RAG pipeline over a handful of scenarios — each crafted to stage a
different failure mode — and sends every trace to the API via the Python SDK.
The server runs the evaluators and assigns the diagnosis, so what shows up in the
dashboard is the platform's *real* verdict, not a label we hard-coded.

Usage (API must be running on :8000):
    python seed_traces.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

# Make the local SDK importable without installing it.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sdks" / "python"))

from traceroai import TraceroClient  # noqa: E402

from rag_pipeline import build_prompt, generate, load_chunks, retrieve  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"

# Each scenario is a real pipeline run; `answer`/`latency_ms` optionally override
# the pipeline output to stage a specific failure the deterministic eval will catch.
SCENARIOS: list[dict] = [
    {
        "name": "healthy_answer",
        "query": "What is the maximum file upload size?",
    },
    {
        "name": "unsupported_claim",
        "query": "How are refunds issued?",
        "answer": "Refunds are settled instantly through blockchain cryptocurrency transfers to your crypto wallet.",
    },
    {
        "name": "retrieval_miss",
        "query": "What is your guaranteed uptime SLA percentage?",
    },
    {
        "name": "semantic_gap",
        "query": "How long does a refund take to process?",
    },
    {
        "name": "latency_spike",
        "query": "How do I reset my password?",
        "latency_ms": 8200,
    },
]


def _chunks_payload(retrieved) -> list[dict]:
    return [
        {
            "rank": i + 1,
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "document_title": chunk.document_title,
            "section": chunk.section,
            "source": chunk.source,
            "final_score": score,
            "text": chunk.text,
        }
        for i, (chunk, score) in enumerate(retrieved)
    ]


def main() -> None:
    client = TraceroClient(base_url=BASE_URL)
    chunks = load_chunks()

    print(f"{'scenario':24} {'diagnosis':18} trace_id")
    print("-" * 78)

    for scenario in SCENARIOS:
        query = scenario["query"]
        top_k = scenario.get("top_k", 3)
        retrieved = retrieve(query, chunks, top_k=top_k)
        answer = scenario.get("answer") or generate(query, retrieved)
        total_ms = scenario.get("latency_ms", 1200)

        trace_id = client.log_trace(
            query={"original": query, "rewritten": query, "rewrite_changed": False},
            retrieval={
                "strategy": "lexical_top_k",
                "config": {"final_top_k": top_k},
                "chunks": _chunks_payload(retrieved),
            },
            generation={
                "provider": "demo",
                "model": "extractive-baseline",
                "answer": answer,
                "answered": not answer.startswith("I'm sorry"),
            },
            prompt={
                "version": "grounded_v1",
                "template_name": "grounded_answer",
                "content": build_prompt(query, retrieved),
            },
            latency={
                "retrieval_ms": 15,
                "generation_ms": max(total_ms - 15, 0),
                "total_ms": total_ms,
            },
            metadata={"scenario": scenario["name"], "top_k": top_k},
        )

        diagnosis = httpx.get(f"{BASE_URL}/v1/traces/{trace_id}").json()["diagnosis"]["label"]
        print(f"{scenario['name']:24} {diagnosis:18} {trace_id}")


if __name__ == "__main__":
    main()