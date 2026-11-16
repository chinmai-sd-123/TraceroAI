# Changelog

Notable changes to the API, dashboard and `traceroai` SDK. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Changed
- The API allows openai 3 (which uses httpx2 internally); the lock installs 3.51.0. Checked
  against the real provider: the diagnosis benchmark gives the same lexical (58.1%) and
  embedding (76.1%) accuracy, and 96.6% for the judge.
- The dashboard summary reads the diagnosis source and cost from stored generated
  columns (migration 0005) instead of parsing every trace's JSON: 147 ms instead of
  777 ms at 50,000 traces. The migration rewrites the traces table once.
- The project is now licensed under Apache-2.0 (previously MIT); see LICENSE and NOTICE.
- TraceroAI is self-hosted only. A deployment of just the landing page and docs (no
  API configured) shows how to run the stack in place of the dashboard and playground.

### Security
- Every read is scoped to the caller's API key: a project key sees only its project,
  admin keys see everything, and without a key (when keys are required) only
  `TRACEROAI_PUBLIC_READ_PROJECTS` are readable.
- API keys can be stored in the database, hashed, and managed with `python -m app.keys`.
- Clients can no longer submit evaluations, diagnoses or feedback with a trace.
- Request bodies are limited (`TRACEROAI_MAX_REQUEST_BYTES`, 1 MB by default), and
  field lengths match the database columns.
- Rate limits keep working without Redis and can't be reset with a forged
  `X-Forwarded-For`; per-key limits on ingest and grading.
- The playground is off unless `TRACEROAI_PLAYGROUND_ENABLED` is set.
- The dashboard upgrades to Next.js 16.4.6, which fixes published remote code execution
  and Proxy bypass advisories, and can be protected with `TRACEROAI_DASHBOARD_PASSWORD`.
- The dashboard sign-in allows 10 wrong passwords per client address in 15 minutes
  (counted per server instance) and has a sign-out button.

### Added
- Database migrations (Alembic), Dockerfiles, and a Docker Compose stack with the API,
  worker and dashboard.
- Diagnoses record their source (`lexical`, `embedding` or `judge`), and traces their
  judge status (`pending`, `complete`, `partial`, `failed` or `skipped`).
- Paginated, filtered trace listing (`GET /v1/traces`, cursor in `X-Next-Cursor`) and
  `GET /v1/metrics/summary`.
- `GET /health/ready` and Prometheus metrics at `/metrics`.
- Trace retention (`TRACEROAI_TRACE_RETENTION_DAYS`) and `DELETE /v1/traces/{id}`.
- `GET /v1/traces` sorts newest first, oldest first or slowest first (`sort=`), and
  filters to one recovery run (`recovery_run_id=`).
- `GET /v1/recovery-runs` lists RecoveryAgent runs with each attempt's diagnosis,
  lever and `top_k`; `GET /v1/metrics/timeseries` gives traces, healthy traces and
  p95 latency per hour or day; the summary counts traces by model and environment.
- The SDK's `trace()` context manager times retrieval, prompt building and generation
  from when each piece is logged, so traces show where the time went.
- Experiments can carry per-question results tied to a variant, and `run_experiment`
  sends them (falling back to variant totals on older servers) and returns them in
  `ExperimentResult.cases`.
- Dashboard layout can be customized and is remembered per browser: the sidebar
  collapses to icons, the trace list and execution timeline can be resized, and the
  overview's panels can be resized, reordered and hidden.
- Docs: an HTTP API reference and a troubleshooting section.
- CI runs a browser smoke test of the production build, including the dashboard with
  its API down.
- `AsyncTraceroClient`, a native asyncio client: traces are sent as tasks on the
  running event loop with the same retries and never-raise behaviour as the sync client.
- The SDK supports Python 3.10 (was 3.11); CI tests 3.10 and 3.14.
- The diagnosis benchmark runs weekly against the real LLM judge (when the repository
  has a provider key) and fails if judge accuracy or self-agreement drops below 90%.
  `python -m app.eval.benchmark` takes `--min-judge-accuracy` and `--min-self-agreement`.
- [What a trace contains](docs/trace-data.md): every field stored, when data goes to
  an LLM provider, and how to remove it.
- A test seeds 50,000 traces and checks every dashboard query stays fast.
- A light dashboard: a trace explorer with sorting, model and environment filters and
  keyboard navigation; a trace page built around the execution timeline; recovery run
  pages; and a per-question grid for experiments.
- A labelled set of 117 traces and a benchmark measuring each evaluation tier
  (`docs/evaluation-benchmark.md`).

### Changed
- `POST /v1/traces` is idempotent on `trace_id`.
- Background evaluation no longer overwrites feedback added while it runs, holds no
  database connection while waiting on the LLM provider, keeps partial judge results,
  and re-queues traces whose job was lost.
- `GET /v1/traces` returns 50 traces per page by default instead of every trace.

### SDK 0.5.0 (unreleased)
- Traces are sent from a background thread and never raise into your code; ids are
  generated client-side and retries reuse them.
- `@client.traced` supports async functions; `aget_trace`, `alog_trace_sync_eval` and
  `aflush` for async code.
- Chunks are normalised before sending (LangChain `Document`s and strings accepted,
  missing ranks and ids filled in).
- `RecoveryAgent` retries only on LLM-judge verdicts by default, groups attempts with a
  run id, takes an optional `rewrite` function, and traces failures in your pipeline.
- `run_experiment` keeps its results when posting them fails.
- The `[recovery]` extra installs only `langgraph`.

## Earlier releases

SDK versions 0.1.0 to 0.4.0 were published to PyPI before this changelog was started;
the git history has the details.
