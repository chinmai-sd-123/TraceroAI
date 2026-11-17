# What a trace contains

TraceroAI stores what your application sends it, in your own Postgres. This page
lists exactly what that is, where it can go, and how to remove it, so you can
decide what is safe to send.

## Stored with every trace

| Part | Fields | Notes |
|---|---|---|
| Question | the user's question, and the rewritten retrieval query if you log one | Verbatim. If your users type personal details into questions, they are stored. |
| Retrieved context | each chunk's text, source, rank, scores and metadata | The full text of every chunk you log. |
| Prompt | the prompt text, version and template name | Only if you call `log_prompt`. |
| Answer | the generated answer, model, provider, temperature and other parameters, token counts | |
| Timing | total latency and per-step timings | |
| Steps | each step's name, kind, timing, status, and any input, output and attributes you send | Steps you send are stored as sent, so a step whose input is a full prompt or tool result stores that too. Steps the server derives hold ids and settings, not text. |
| Project | project id, environment, pipeline version | |
| Metadata | whatever you pass as `metadata=` | Free-form. Recovery runs add a run id and attempt number here. |

## Added by the server

- **Evaluations and diagnosis:** scores, the judge's reasons, and the claims it
  extracted from the answer (quoted from the answer).
- **Feedback:** a thumbs up or down and an optional comment of up to 2,000 characters.
- **Time received.**

The server doesn't store the caller's IP address or user agent with a trace. The
address is used only for short-lived rate-limit counters (in Redis, or in memory
when Redis isn't configured) that expire within minutes.

## Where it can go

- **Your database.** Traces live in the `traces` table of the Postgres you configure.
- **Your LLM provider, only if you configure one.** With `TRACEROAI_OPENAI_API_KEY`
  (or `TRACEROAI_JUDGE_BASE_URL`) set, the background evaluation sends the question,
  the retrieved chunks and the answer to that provider for embeddings and the LLM
  judge. Without a provider key nothing leaves your servers, and diagnoses are
  term-overlap estimates. Point `TRACEROAI_JUDGE_BASE_URL` at a model you host to
  keep judging in-house.
- **Nowhere else.** TraceroAI sends no telemetry of its own.

## Keeping less

- Don't log what you don't need: `log_prompt` is optional, and chunk text can be
  trimmed before you pass it to `log_retrieval`.
- Remove personal data before it leaves your application with the SDK's `redact=`
  hook: a function that gets a copy of each trace and returns the trace to send, or
  None to drop it. `redact_strings(mask_emails)` masks email addresses in every field
  that can hold user text. If the function fails, the trace is dropped, never sent
  unredacted. Traces sent over OpenTelemetry are redacted in your exporter pipeline
  instead.
- Use project keys so each application reads only its own traces.

## Removing it

- **Automatically:** set `TRACEROAI_TRACE_RETENTION_DAYS`. The worker deletes traces
  older than that every hour. Without the worker (no Redis), run
  `python -m app.retention` from `services/api` on a schedule, for example a daily cron.
- **One trace:** `DELETE /v1/traces/{trace_id}`. A project key can delete only its own
  project's traces; an admin key, any.
- **Everything for a project:** `DELETE FROM traces WHERE project_id = '...'` in
  Postgres.
