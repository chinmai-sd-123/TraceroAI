# 1. Position TraceroAI as failure diagnosis, not a broad observability platform

- Status: accepted
- Date: 2026-11-16

## Context

TraceroAI started as RAG tracing with a diagnosis attached. Before planning P3 we asked
whether to broaden it into an AI or agent observability platform.

What we found:

- Collecting traces is becoming a commodity. OpenTelemetry's GenAI conventions, Langfuse
  (MIT, acquired by ClickHouse in January 2026), LangSmith and the APM vendors all record
  LLM and agent traces. Competing on breadth means competing with teams many times our
  size.
- What those tools mostly leave to the user is the step from "this run was bad" to "this
  step caused it". Commercial products are starting to automate it; no open-source,
  self-hostable tool does it by default.
- TraceroAI already does that for RAG, records whether a judge or an estimate decided,
  and publishes how accurate each is. That is the distinctive part.
- RAG alone is a shrinking label: retrieval is increasingly one tool inside an agent.

## Decision

TraceroAI is the diagnosis layer for RAG pipelines and agents: it finds the step that
broke and shows the evidence. It accepts traces from its own SDK and (planned) from
OpenTelemetry, so it can work beside an existing tracing tool.

We will extend diagnosis from RAG stages to agent steps, and build what turns a diagnosis
into a fix (issues, alerts, datasets, a regression gate). We will not build prompt
management, an LLM gateway, a playground, a hosted cloud, or a general dashboard builder.

## Consequences

- P3 starts with the step data model, OpenTelemetry ingest and agent diagnosis
  (see ADR 2), not with more RAG features.
- Agent diagnosis must be measured on a labelled set before the site claims it, as RAG
  diagnosis was.
- The site and docs lead with the cause, and mark planned features as planned.
- Users who want an all-in-one platform will choose something else; that is accepted.
