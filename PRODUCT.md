# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

An AI engineer on a team of 2 to 20 at a startup or scale-up, with a RAG feature or an
agent in production, who wants to run their tooling on their own servers. Individual
developers trying it on a side project are how most people will find it. They come to
TraceroAI when a run went wrong, or before shipping a change, to find out which step
failed and whether a change (top_k, prompt, model, tool description) fixed it. They
already have a pipeline or agent (their own code, LangChain, LlamaIndex or LangGraph)
and may already send traces to another tool.

## Product Purpose

TraceroAI finds the step that broke a RAG pipeline or an agent, and shows the evidence.
It takes in a trace, checks the steps that matter, and gives one diagnosis: the failing
step, the reason, and whether an LLM judge or a cheaper estimate decided it. Success for
the user: "this run was bad" becomes "this step caused it" in one click, and a fix can
be shown to work before it ships.

## Positioning

- **The cause, not just the trace.** Collecting traces is becoming a standard; naming
  the step that failed is the product. Every trace gets one diagnosis tied to a step.
- **How sure, and how often right.** Each diagnosis says whether the judge or an
  estimate made it, and the accuracy of each is measured on a labelled set and
  published, including where it is wrong.
- **Works beside what teams already use.** Traces can come from the Python SDK or any
  OpenTelemetry source (OpenInference or OpenTelemetry GenAI conventions), so TraceroAI
  can sit next to Langfuse, LangSmith or an APM instead of replacing them.
- **Failure to fix.** Repeated failures group into issues; recovery runs retry the step
  that failed; experiments compare variants on labelled questions; (planned) issues
  become regression tests.
- **Open source and self-hosted.** Apache-2.0. Postgres and one Docker Compose command;
  traces stay on the user's infrastructure.

Not the goal: a broad observability or LLMOps platform (prompt management, gateways,
playgrounds, hosted cloud). Those are well served elsewhere.

## Operating Context

- The engineer works from their editor and terminal, sends traces from code, and opens
  the dashboard to inspect a specific trace (often from a trace id in their logs) or to
  check how a project is doing.
- Typical loop: notice a bad run, open its trace, read which step failed and why (the
  judge's reason, the chunks or tool results involved), change the pipeline, compare
  with an experiment.
- The dashboard runs locally (Docker Compose) or self-hosted behind a password. There is
  no hosted service.

## Capabilities and Constraints

- Today: RAG traces from the Python SDK (sync and async), the HTTP API, or OpenTelemetry
  (OTLP/HTTP; tested with LangChain and LangGraph through OpenInference). Traces have steps. Runs that
  aren't RAG runs (agents) are stored with their steps and marked "not diagnosed". Diagnoses: healthy answer,
  correct refusal, retrieval miss, unsupported claim, wrong answer, needs review.
  Sources: lexical, embedding, judge. Judge status: pending, complete, partial, failed,
  skipped. Issues (failures grouped by cause, with open, resolved and regressed states),
  recovery runs, experiments with per-question results, tokens and cost (per model call,
  per run, and per healthy answer), an agent run view (steps, tool calls, errors),
  alerts to a webhook, redaction in the SDK, feedback, retention, and bundled demo data.
- Planned (P3), not yet built: agent failure diagnosis, datasets and a regression gate.
  Nothing planned may be presented as available.
- Without a configured LLM judge, every diagnosis is an estimate; the interface must say
  so rather than present it as fact.
- Stack: Next.js (App Router, server components) and Tailwind CSS in `traceroai-web`;
  FastAPI and Postgres in `services/api`. Dashboard reads use a server-side API key.
- Access today: project and admin API keys, and an optional shared dashboard password.
  User accounts and roles are planned.

## Brand Commitments

- Name: TraceroAI. The identity is the "Investigation Docket" (see DESIGN.md): a light,
  report-like look, navy for everything interactive, red only for the probable cause.
- The whole site stays light (user decision, 2026-11-16). It should still feel unlike any
  other site in the category: precision, a continuous story, the real product as the
  illustration.

## Evidence on Hand

- Measured diagnosis accuracy per evaluation tier on 117 labelled traces:
  `docs/evaluation-benchmark.md`, raw report in `docs/benchmarks/`. Re-run weekly.
- SDK on PyPI (`traceroai`), source on GitHub, Apache-2.0.
- No customers, testimonials, logos, usage numbers or press exist. Never invent them.

## Product Principles

1. Show the cause, not just the score: lead with which step failed and why.
2. Say how sure we are: every diagnosis shows whether the judge or an estimate made it.
3. Get to the failing step fast: the path from "something's wrong" to the evidence is short.
4. Never fabricate: no placeholder numbers, invented results, or claims without data.
5. Claim only what ships: planned features are labelled as planned.
6. The developer's data stays theirs: nothing assumes a hosted service.
