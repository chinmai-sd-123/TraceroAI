# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

An AI engineer, alone or in a small team, building a retrieval-augmented generation
(RAG) feature into their own application. They come to TraceroAI when an answer is
wrong, or before shipping a change, to find out why answers fail and whether a change
(top_k, prompt, model) made them better. They already have a RAG pipeline (their own
code, LangChain or LlamaIndex) and add the Python SDK to it.

## Product Purpose

TraceroAI traces each RAG answer (query, retrieved chunks, prompt, generation, latency,
cost), evaluates it, and diagnoses which stage of the pipeline failed. Success for the
user: a bad answer becomes a lookup ("retrieval missed the refund policy") rather than a
guess, and a pipeline change can be shown to help before it ships.

## Positioning

- **Which stage failed.** Every answer gets one diagnosis tied to a pipeline stage:
  retrieval, grounding, or the answer itself, not only a score.
- **Self-healing recovery.** An optional agent retries the stage that failed (retrieve
  more, or regenerate with a stricter prompt), and every attempt is traced as one run.
- **Honest evaluation.** Each diagnosis records whether the LLM judge made it or a cheap
  estimate (embedding similarity, term overlap), and each tier's accuracy is measured on
  a labelled set and published.
- **Open source and self-hosted.** One Docker Compose command runs the whole stack; the
  user's traces stay on their infrastructure.

## Operating Context

- The engineer works from their editor and terminal, sends traces from code with the
  SDK, and opens the dashboard to inspect a specific trace (often from a trace id in
  their logs) or to check how a project is doing.
- Typical loop: notice a bad answer, find its trace, read which stage failed and why
  (the judge's reason, the chunks that were retrieved), change the pipeline, compare.
- Experiments (`run_experiment`) compare pipeline variants on a labelled dataset and
  show up as eval runs.
- The dashboard may run locally (Docker Compose), self-hosted behind a password, or as
  the public demo.

## Capabilities and Constraints

- Diagnoses: healthy answer, correct refusal, retrieval miss, unsupported claim, wrong
  answer, needs review. Sources: lexical, embedding, judge. Judge status: pending,
  complete, partial, failed, skipped.
- Data: traces (paginated, filterable by diagnosis, model, environment, text, time),
  a summary computed over all traces, eval runs (experiments and regression runs),
  feedback, recovery runs, projects.
- Without a configured LLM judge, every diagnosis is an estimate; the interface must
  say so rather than present it as fact.
- Stack: Next.js (App Router, server components) and Tailwind CSS in `traceroai-web`;
  data from the FastAPI service. Dashboard reads use a server-side API key.
- Undecided: user accounts and roles (today: API keys and an optional shared dashboard
  password).

## Brand Commitments

- Name: TraceroAI. No logo, colour system or voice guide exists yet.
- The dashboard uses a light theme (user request, 2026-11-14).

## Evidence on Hand

- Measured diagnosis accuracy per evaluation tier on 117 labelled traces:
  `docs/evaluation-benchmark.md`, raw report in `docs/benchmarks/`.
- Public demo at https://www.traceroai.tech, SDK on PyPI (`traceroai`), source on GitHub.
- No customers, testimonials, logos, usage numbers or press exist. Never invent them.

## Product Principles

1. Show the cause, not just the score: lead with which stage failed and why.
2. Say how sure we are: every verdict shows whether the judge or an estimate made it.
3. Get to the trace fast: the path from "something's wrong" to the failing trace is short.
4. Never fabricate: no placeholder numbers, invented results, or claims without data.
5. The developer's data stays theirs: nothing in the product assumes a hosted service.
