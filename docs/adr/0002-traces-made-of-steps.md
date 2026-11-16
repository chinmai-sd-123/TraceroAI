# 2. Store a trace as a summary row plus a tree of steps

- Status: accepted
- Date: 2026-11-16

## Context

Today a trace is one flat RAG interaction: the question, the retrieved chunks, one prompt
and one answer, stored as a JSON document in a `traces` row. That shape can't hold an
agent (several model calls, tool calls, nesting) or anything sent over OpenTelemetry,
which arrives as spans with parents.

Options considered:

1. Keep one JSON document per trace and nest steps inside it. Simple, but every step
   query parses whole documents (the summary already took 0.8 s at 50,000 traces before
   migration 0005 moved two fields into columns), and partial traces arriving over time
   need read-modify-write.
2. A separate analytics database (ClickHouse) for steps now. Fast, but a second database
   to run before any user has needed it.
3. Postgres: keep `traces` as the summary row and add a `spans` table for the steps.

## Decision

Option 3. `traces` stays as one row per run with the fields lists and summaries need
(diagnosis, cost, latency, project). A new `spans` table holds the steps: trace id, step
id, parent, kind (agent, model call, tool, retriever), start and end, status, input,
output and attributes. Steps are partitioned by month so retention can drop a partition.

The existing SDK payload keeps working: the server turns it into steps. Traces that
arrive as spans over time are assembled until the root step ends or the trace goes quiet,
then diagnosed.

ClickHouse is not adopted. We revisit when the scale test, run at 5 million steps, misses
its bound.

## Consequences

- One database to run, as before.
- A migration and a new assembly step in ingest; all existing API tests must pass
  unchanged.
- Checks and diagnosis move from fixed RAG fields to steps by kind, which is what makes
  agent failure types possible.
- The scale test grows to cover steps (500,000 first, 5 million for the ClickHouse
  decision).
