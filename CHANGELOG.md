# Changelog

Notable changes to the API, dashboard and `traceroai` SDK. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

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

### Added
- Database migrations (Alembic), Dockerfiles, and a Docker Compose stack with the API,
  worker and dashboard.
- Diagnoses record their source (`lexical`, `embedding` or `judge`), and traces their
  judge status (`pending`, `complete`, `partial`, `failed` or `skipped`).
- Paginated, filtered trace listing (`GET /v1/traces`, cursor in `X-Next-Cursor`) and
  `GET /v1/metrics/summary`.
- `GET /health/ready` and Prometheus metrics at `/metrics`.
- Trace retention (`TRACEROAI_TRACE_RETENTION_DAYS`) and `DELETE /v1/traces/{id}`.
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
