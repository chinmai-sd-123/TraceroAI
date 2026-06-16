# TraceroAI — System Design

> **Status (June 2026):** The RAG debugger is built and deployed end-to-end —
> ingestion API, Python SDK (published to PyPI), Postgres storage, deterministic
> *and* LLM-as-judge evaluation, automatic diagnosis, the Next.js dashboard, a
> public live playground, and a sample monitored RAG app are all live. The
> experiment/MLOps layer and the LangGraph recovery layer are the next
> milestones — see the [Roadmap](#roadmap) at the end.
>
> This document describes the system as built and where it is going.

## Product Definition

TraceroAI is a RAG observability and evaluation platform for production AI systems.

The core product promise:

```text
When a RAG answer is wrong, TraceroAI shows whether the failure came from retrieval, context, prompting, generation, or evaluation.
```

TraceroAI is not a chatbot. It is reliability infrastructure around RAG and LLM applications.

The initial product is a RAG Debugger.

The future direction is RAG and agent workflow observability.

## Core Mental Model

A bad RAG answer is only the symptom. TraceroAI should expose the cause.

The complete lifecycle:

```text
user query
-> query rewrite
-> routing / metadata filtering
-> retrieval
-> reranking
-> prompt construction
-> generation
-> evaluation
-> diagnosis
-> feedback
```

Most beginner RAG projects log only:

```text
query + answer
```

TraceroAI should log:

```text
why the answer happened
```

That means capturing the query, rewritten query, retrieval strategy, retrieved chunks, scores, prompt, model output, evaluation results, diagnosis, and feedback.

## High-Level Architecture

```text
Sample RAG App
   |
   | Python SDK captures trace
   v
FastAPI Ingestion API
   |
   | validates and stores trace
   v
Postgres
   |
   | enqueue evaluation job
   v
Redis Queue
   |
   v
Evaluation Worker
   |
   | groundedness, relevance, diagnosis
   v
Postgres
   |
   v
Next.js Dashboard
```

Later additions:

```text
Object Storage
LangGraph recovery workflow
Experiment comparison
ClickHouse analytics
OpenTelemetry compatibility
```

## Repository Structure

```text
TraceroAI/
  traceroai-web/
    src/
      app/
        page.tsx
        case-study/
          page.tsx
        dashboard/
          page.tsx
        dashboard/traces/
          page.tsx
        dashboard/traces/[traceId]/
          page.tsx
        dashboard/eval-runs/
          page.tsx
      components/
      lib/
    package.json

  services/
    api/
      app/
        main.py
        api/
          routes/
            health.py
            traces.py
            eval_runs.py
            feedback.py
        core/
          config.py
          security.py
        schemas/
          traces.py
          evaluations.py
          eval_runs.py
        db/
          session.py
          models.py
        services/
          trace_ingestion.py
          evaluation_jobs.py
      tests/
      pyproject.toml

    worker/
      app/
        main.py
        evaluators/
          groundedness.py
          answer_relevance.py
          context_relevance.py
          source_recall.py
          diagnosis.py
        jobs/
          evaluate_trace.py
      tests/
      pyproject.toml

  sdks/
    python/
      traceroai/
        __init__.py
        client.py
        schemas.py
        trace.py
      pyproject.toml

  examples/
    rag-demo/
      documents/
      app.py
      rag_pipeline.py
      seed_traces.py

  infra/
    docker-compose.yml

  docs/
    architecture.md
    trace-model.md
    evaluation-design.md
    traceroai-system-plan.md

  README.md
  .env.example
```

## Main Components

### Python SDK

The SDK makes TraceroAI feel like a real developer tool. It lets any RAG application send traces without handcrafting JSON.

MVP usage:

```python
from traceroai import TraceroClient

client = TraceroClient(
    api_key="dev-key",
    base_url="http://localhost:8000",
)

client.log_trace(
    user_query=query,
    retrieved_chunks=chunks,
    prompt=prompt,
    final_answer=answer,
    model_name="gpt-4o-mini",
    metadata={
        "top_k": 5,
        "prompt_version": "v1",
    },
)
```

Future usage:

```python
with client.trace(user_query=query) as trace:
    trace.log_retrieval(chunks)
    trace.log_prompt(prompt)
    trace.log_generation(answer, model_name="gpt-4o-mini")
```

### FastAPI Backend

The backend accepts traces, validates payloads, stores trace data, and exposes dashboard APIs.

Initial endpoints:

```text
GET  /health
POST /v1/traces
GET  /v1/traces
GET  /v1/traces/{trace_id}
```

Later endpoints:

```text
POST /v1/traces/{trace_id}/feedback
GET  /v1/eval-runs
POST /v1/eval-runs
GET  /v1/eval-runs/{eval_run_id}
```

### Postgres

MVP tables:

```text
traces
retrieved_chunks
evaluations
```

Production-style tables:

```text
projects
api_keys
traces
retrieved_chunks
reranked_chunks
evaluations
diagnoses
feedback
eval_datasets
eval_cases
eval_runs
pipeline_configs
```

### Redis and Worker

Evaluations can be slow, especially LLM-as-judge checks. Trace ingestion should return quickly.

Flow:

```text
trace received
-> trace stored
-> evaluation job queued
-> worker evaluates
-> evaluation results saved
```

### Next.js Dashboard

The current `traceroai-web` app becomes both public product site and dashboard.

Routes:

```text
/
  Product homepage

/case-study
  Technical explanation and build case study

/dashboard
  Overview

/dashboard/traces
  Trace list

/dashboard/traces/[traceId]
  Trace detail

/dashboard/eval-runs
  Experiment and eval run comparison
```

Trace detail is the heart of the product.

It should show:

```text
query
rewritten query
retrieval strategy/config
retrieved chunks
prompt metadata
answer
latency
evaluation scores
claim-level support
diagnosis
suggested fix
```

## Single Trace Schema

The single-trace schema is inspired by the `9b3eccb6-3de2-4abf-9356-ddbae8fdc789.json` file.

That JSON is a single RAG trace and should be used as the main trace design reference.

Recommended shape:

```json
{
  "schema_version": "tracero_trace_v1",
  "trace_id": "uuid",
  "timestamp": "2026-05-22T07:40:25.429942+00:00",
  "status": "answered",
  "project": {
    "project_id": "demo-rag",
    "environment": "dev"
  },
  "query": {
    "original": "Can admins change the workspace region themselves?",
    "rewritten": "Can admins change the workspace region themselves?",
    "rewrite_changed": false,
    "rewrite_method": "rule_based_v1",
    "rewrite_version": "query_rewrite_rule_based_v1"
  },
  "retrieval": {
    "strategy": "hybrid_rrf_rerank",
    "config": {
      "lexical_top_k": 5,
      "dense_top_k": 5,
      "final_top_k": 3,
      "fusion": "rrf",
      "reranker": "rule_based_v1"
    },
    "chunks": [
      {
        "rank": 1,
        "chunk_id": "product_faq_2",
        "document_id": "product_faq",
        "document_title": "Product FAQ",
        "section": "Can I change my workspace region?",
        "source": "product_faq.md",
        "base_score": 0.0327,
        "final_score": 1.0827,
        "rrf_score": 0.0327,
        "lexical_rank": 1,
        "dense_rank": 1,
        "lexical_score": 0.6101,
        "dense_score": 0.4700,
        "text": "Full chunk text",
        "text_preview": "Preview text"
      }
    ]
  },
  "prompt": {
    "version": "grounded_prompt_v2",
    "template_name": "grounded_answer_prompt",
    "content": "Full prompt or prompt preview"
  },
  "generation": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0,
    "answer": "No, admins cannot change the workspace region themselves...",
    "answered": true
  },
  "latency": {
    "retrieval_ms": 17,
    "prompt_build_ms": 0,
    "generation_ms": 1154,
    "total_ms": 1171
  },
  "evaluations": {
    "quick": {
      "groundedness": {
        "label": "grounded",
        "unsupported_claims": [],
        "reason": "No obvious unsupported claims were detected."
      },
      "context_relevance": {
        "verdict": "good_context",
        "summary": {
          "total_chunks": 3,
          "relevant_chunks": 2,
          "partially_relevant_chunks": 0,
          "irrelevant_chunks": 1
        },
        "chunks": []
      },
      "answer_relevance": {
        "label": "relevant",
        "reason": "The answer discusses workspace region changes."
      },
      "diagnosis": {
        "label": "healthy_answer",
        "reason": "The retriever found useful context and the model answered the question."
      }
    },
    "deep": {
      "status": "completed",
      "claim_groundedness": {
        "label": "grounded",
        "claims": [
          {
            "claim": "admins cannot change the workspace region themselves",
            "supported": true,
            "evidence_blocks": [1, 2],
            "reason": "The context states customers cannot directly change a workspace region after creation."
          }
        ],
        "unsupported_claims": []
      },
      "evaluated_at": "2026-05-22T07:45:06.167120+00:00"
    }
  },
  "feedback": []
}
```

Important trace fields to keep:

```text
retrieval_strategy
retrieval_config
lexical_score
dense_score
rrf_score
final_score
context relevance per chunk
quick evaluations
offline/deep evaluations
claim-level groundedness
latency breakdown
diagnosis label
```

## Eval Run Schema

The eval-run schema is inspired by the `768f13bd-9d8c-43de-9938-1e2de7f47338.json` file.

That JSON is not a single trace. It is an evaluation run containing many traces across different `top_k` configurations.

Use it for:

```text
Eval run schema
Experiment comparison
Dashboard demo data
MLOps storytelling
README case study
```

Recommended shape:

```json
{
  "schema_version": "tracero_eval_run_v1",
  "eval_run_id": "uuid",
  "timestamp": "2026-06-01T18:21:06.559003+00:00",
  "dataset_name": "acme_policy_eval",
  "model": {
    "provider": "openai",
    "name": "gpt-4o-mini",
    "temperature": 0
  },
  "experiment": {
    "parameter": "top_k",
    "values": [1, 2, 3, 5],
    "metadata_filters": {
      "enabled": true,
      "method": "rule_based_category_router_v1"
    }
  },
  "runs": [
    {
      "top_k": 3,
      "summary": {
        "total_cases": 5,
        "source_recall_rate": 1.0,
        "healthy_rate": 1.0,
        "avg_context_precision": 1.0,
        "avg_latency_ms": 1942
      },
      "trace_results": []
    }
  ],
  "recommendation": {
    "recommended_top_k": 3,
    "reason": "Selected the top_k with the highest healthy rate, then preferred cleaner context precision, lower latency, and smaller top_k.",
    "metrics": {
      "healthy_rate": 1.0,
      "source_recall_rate": 1.0,
      "avg_context_precision": 1.0,
      "avg_latency_ms": 1942
    }
  }
}
```

Important eval-run fields to keep:

```text
schema_version
run_id / eval_run_id
timestamp
top_k_values
metadata_filters
model config
runs grouped by config
summary metrics
per-case results
recommendation
```

Dashboard table example:

```text
top_k | healthy_rate | source_recall | context_precision | avg_latency
1     | 0.80         | 1.00          | 1.00              | 2631ms
2     | 1.00         | 1.00          | 1.00              | 2152ms
3     | 1.00         | 1.00          | 1.00              | 1942ms
5     | 1.00         | 1.00          | 1.00              | 2731ms
```

## Evaluation Types

Start with:

```text
context_relevance
groundedness
answer_relevance
```

Then add:

```text
source_recall
unsupported_claim_detection
latency_cost
answer_correctness
claim_groundedness
```

Each evaluation result should store:

```text
trace_id
evaluator_name
evaluator_version
score
label
reason
created_at
```

## Quick vs Deep Evaluation

TraceroAI should separate quick evaluations from deeper offline evaluations.

Quick evaluation:

```text
runs soon after trace ingestion
mostly rule-based or lightweight
fast enough for dashboard feedback
```

Deep evaluation:

```text
runs asynchronously
can use LLM-as-judge
can perform claim extraction
can compare answer claims against evidence blocks
```

This distinction makes the system feel production-grade.

## Diagnosis Labels

Every trace is reduced to exactly one of six diagnosis labels:

```text
healthy_answer      retrieval, grounding, and relevance all pass
correct_refusal     model correctly declined when context didn't support an answer
retrieval_miss      retrieved context doesn't match the query
unsupported_claim   answer asserts things the context doesn't support
wrong_answer        answer doesn't address the query
needs_review        mixed signals — flagged for a human
```

The diagnosis reducer evaluates in priority order (a correct refusal short-circuits
before the failure checks, so a model declining on weak context is never mislabeled
as a failure):

```text
if refused (no answer or a refusal phrase):  correct_refusal
elif context_relevance == fail:              retrieval_miss
elif groundedness == fail:                   unsupported_claim
elif answer_relevance == fail:               wrong_answer
elif all three pass:                         healthy_answer
else:                                        needs_review
```

Implemented in `services/api/app/evaluators/diagnosis.py`. Additional signals
(latency spikes, cost) surface as dashboard metrics rather than diagnosis labels.

## Dashboard Plan

### Public Homepage

The current deployed site stays as the product/case-study shell.

### Case Study Page

Explain:

```text
problem
system architecture
trace model
evaluation design
production tradeoffs
```

### Dashboard Overview

Show:

```text
total traces
healthy rate
failure distribution
average latency
recent eval runs
```

### Trace List

Show:

```text
query
status
diagnosis label
model
latency
timestamp
```

### Trace Detail

Show:

```text
query and rewrite
retrieval strategy/config
retrieved chunks table
prompt preview
answer
latency breakdown
quick evaluations
deep evaluations
claim support table
diagnosis
suggested fix
```

### Eval Runs

Show experiment comparison:

```text
top_k comparison
filters on/off
reranker on/off
prompt v1 vs prompt v2
recommended config
```

## Sample RAG Demo

The demo app should create meaningful traces, not random data.

Seed scenarios:

```text
1. Healthy answer
2. Retrieval miss
3. Unsupported claim
4. Noisy context
5. Wrong answer
6. Latency spike
```

Use a small fake product documentation set, for example:

```text
refund_policy.md
support_policy.md
onboarding_guide.md
product_faq.md
security_policy.md
```

## Experiment Layer

> **Planned** (Roadmap item 1). The eval-run *schema* and dashboard for this are
> already built; the run generator and winner selection are what remain.

Compare:

```text
top_k=1 vs top_k=2 vs top_k=3 vs top_k=5
filters off vs filters on
reranker off vs reranker on
prompt_v1 vs prompt_v2
```

Metrics:

```text
healthy_rate
groundedness_avg
context_relevance_avg
source_recall_rate
avg_context_precision
avg_latency_ms
recommended_config
```

This is the MLOps layer and should be one of the strongest portfolio signals.

## LangGraph Layer

> **Planned** (Roadmap item 3). Designed to be added after the core debugger —
> which is now done.

Workflow:

```text
query
-> retrieve
-> generate
-> evaluate
-> if retrieval_miss: retry with rewritten query or higher top_k
-> if unsupported_claim: regenerate with stricter grounding prompt
-> if still failing: mark needs_review
```

This makes TraceroAI attractive for agentic AI roles without distracting from the core debugger.

## Build Status

The core RAG debugger is built and deployed. Progress against the original milestones:

| # | Milestone | Status |
|---|---|---|
| 1 | API ingestion (`/health`, `POST /v1/traces`, trace schema) | ✅ Done |
| 2 | Python SDK (`log_trace`, context-manager, decorator) — published to PyPI | ✅ Done |
| 3 | Storage — Postgres (traces persisted as JSONB) | ✅ Done |
| 4 | Dashboard screens (trace list, trace detail, eval runs) | ✅ Done |
| 5 | Dashboard ↔ FastAPI integration | ✅ Done |
| 6 | Evaluators (groundedness, context/answer relevance, diagnosis) | ✅ Done |
| 7 | Sample monitored RAG app | ✅ Done |
| 8 | Eval runs (datasets, variant comparison, summary metrics) | 🔶 Mostly done — schema, ingest/CRUD, and dashboard exist; a run *generator* + recommendation logic remain |
| 9 | LangGraph recovery workflow | ⬜ Planned |
| 10 | Portfolio polish (README, diagram, screenshots, demo, CI) | 🔶 README + architecture diagram + screenshots done; CI + demo video remain |

**Shipped beyond the original plan:** provider-agnostic LLM judge (OpenAI *or*
Gemini via one config), a public interactive `/docs` playground, the quick→deep
diagnosis correction, multi-tenant-lite project API keys, and a per-IP rate limiter
on the public endpoint.

## Roadmap

What's next, roughly in order:

1. **Eval runs (complete the loop)** — a harness that *generates* runs by replaying a
   dataset across pipeline configs (`top_k`, prompt, reranker), plus a `recommended_config`
   winner. The Experiment Layer above is the design for this — the MLOps story.
2. **Cost tracking** — capture token usage + estimated cost per trace and aggregate it
   on the dashboard (surfaced as a metric, alongside latency).
3. **LangGraph recovery** — the self-healing workflow in the LangGraph Layer above:
   `evaluate → retry/regenerate → needs_review`. The agentic-AI signal.
4. **OpenTelemetry** — OTel-compatible export so traces flow into standard observability
   tooling. The "real infrastructure" signal.

### Deliberately out of scope (for now)

```text
billing · enterprise auth · ClickHouse analytics · complex multi-agent systems
full multi-tenant SaaS · too many dashboard pages
```

The debugger comes first; these are scale concerns, not learning-project concerns.
