# TraceroAI — Complete Engineering Handbook

---

# PART 1 — PROJECT OVERVIEW

## Purpose

TraceroAI is a **RAG (Retrieval-Augmented Generation) observability, evaluation, and self-healing platform**. It is the diagnostic layer between a RAG pipeline and its users — when a RAG system produces a bad answer, TraceroAI determines *which stage* failed (retrieval, context, prompting, or generation) instead of treating the symptom as a generic "hallucination."

## Problem Being Solved

In production RAG systems, a wrong answer is a **symptom**, not a diagnosis. The answer could be wrong because:
- The retriever fetched irrelevant documents (**retrieval miss**)
- The retrieved context was right but the model fabricated claims beyond it (**unsupported claim**)
- The answer didn't address the question at all (**wrong answer**)
- The model correctly declined because the KB lacked the info (**correct refusal**)

Without per-stage observability, teams resort to ad-hoc debugging — reading logs, guessing, and rerunning queries. TraceroAI automates this into a structured evaluation → diagnosis → (optionally) recovery pipeline.

## Target Users

- **AI/ML engineers** building RAG applications who need production-grade observability
- **Platform teams** evaluating RAG pipeline configs (top_k, prompt versions, models) via A/B experiments
- **QA engineers** running regression gates on golden datasets before shipping pipeline changes

## Core Functionality

1. **Trace ingestion** — Capture the full lifecycle of a RAG answer: query, retrieval (chunks, strategy, config), prompt, generation (answer, model, tokens), and latency
2. **Two-tier evaluation** — Fast embedding-cosine relevance (synchronous, every trace) + LLM-as-judge claim-level groundedness (asynchronous, deep analysis)
3. **Six-label diagnosis** — Each trace is reduced to one of: `healthy_answer`, `correct_refusal`, `retrieval_miss`, `unsupported_claim`, `wrong_answer`, `needs_review`
4. **Self-healing recovery agent** — A LangGraph state machine that retries the failed stage: re-retrieves on a miss, re-generates with a stricter prompt on an unsupported claim
5. **Experiment harness** — Replay a labeled dataset across pipeline variants, grade each with the server-side judge, pick the best config
6. **Cost tracking** — Server-owned token + USD cost computation from a community-maintained price table
7. **Multi-tenant project scoping** — API key → project_id mapping; traces are isolated per project on the dashboard
8. **Dashboard** — Next.js frontend showing overview metrics, trace list/detail, eval runs, failure mix, recovery insights

## Business Value

- **Reduce mean-time-to-diagnosis** from hours of manual log reading to seconds of structured evaluation
- **Prevent regressions** with golden-dataset regression gates (deterministic baseline 8/9 on the golden set; see *Measured Results* in Part 9)
- **Automate recovery** — the LangGraph agent retries failed traces without human intervention
- **Enable A/B testing** for RAG configs — data-driven decisions on retrieval strategy, prompt version, model

## Technical Goals

- **No vendor lock-in**: The LLM judge works with OpenAI or any OpenAI-compatible endpoint (Gemini, etc.) via a single `base_url` config
- **Fail-open everywhere**: Embedding API down → lexical fallback. Redis down → BackgroundTasks fallback. Judge down → deterministic diagnosis. Telemetry failure → warn, never crash the caller
- **Server owns truth**: The SDK sends raw data (query, chunks, answer, tokens); the server computes evaluations, diagnosis, and cost. No client-side grading or pricing
- **Separation of platform and pipeline**: The user's RAG pipeline is injected via dependency injection (retrieve/generate callables). The platform owns schema, ingestion, evaluation, and dashboard

---

# PART 2 — HIGH-LEVEL ARCHITECTURE

## Architecture Explanation

TraceroAI follows a **three-tier architecture**: SDK (client) → API (server) → Dashboard (frontend), with asynchronous deep evaluation offloaded to a Redis-backed worker.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER'S RAG APPLICATION                       │
│                                                                     │
│   retrieve(query, top_k) ──→ generate(query, context) ──→ answer   │
│         │                            │                              │
│         └──── traceroai SDK ─────────┘                              │
│              (context manager / decorator / log_trace)              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ HTTP POST /v1/traces
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FASTAPI INGESTION SERVER                        │
│                                                                     │
│  ┌──────────┐   ┌───────────────┐   ┌──────────────┐               │
│  │ Tenancy  │──▶│ Cost Compute  │──▶│ Quick Eval   │               │
│  │ (API key │   │ (price table) │   │ (embedding + │               │
│  │  → proj) │   └───────────────┘   │  lexical)    │               │
│  └──────────┘                       └──────┬───────┘               │
│                                            │                        │
│                                  ┌─────────▼─────────┐             │
│                                  │    Diagnosis       │             │
│                                  │ (6-label reducer)  │             │
│                                  └─────────┬─────────┘             │
│                                            │                        │
│                              ┌─────────────▼──────────────┐        │
│                              │   Save to Postgres (JSONB) │        │
│                              └─────────────┬──────────────┘        │
│                                            │                        │
│                         ┌──────────────────┼──────────────────┐     │
│                         │ Redis available? │ No               │     │
│                         ▼ Yes              ▼                  │     │
│                   ┌───────────┐    ┌──────────────┐           │     │
│                   │ LPUSH to  │    │ Background   │           │     │
│                   │ Redis     │    │ Tasks (in-   │           │     │
│                   │ queue     │    │ process)     │           │     │
│                   └─────┬─────┘    └──────┬───────┘           │     │
│                         │                 │                   │     │
└─────────────────────────┼─────────────────┼───────────────────┘     │
                          │                 │                         │
                          ▼                 ▼                         │
                   ┌─────────────────────────────┐                    │
                   │      DEEP EVAL WORKER       │                    │
                   │ (BRPOP loop / BackgroundTask)│                   │
                   │                             │                    │
                   │  ┌────────────────────────┐ │                    │
                   │  │ LLM Judge (OpenAI SDK) │ │                    │
                   │  │ - claim groundedness   │ │                    │
                   │  │ - context relevance    │ │                    │
                   │  │ - answer relevance     │ │                    │
                   │  │ - correctness grading  │ │                    │
                   │  └────────────┬───────────┘ │                    │
                   │               │             │                    │
                   │  ┌────────────▼───────────┐ │                    │
                   │  │ Re-diagnose from judge │ │                    │
                   │  │ (overwrites quick diag)│ │                    │
                   │  └────────────┬───────────┘ │                    │
                   │               │             │                    │
                   │  ┌────────────▼───────────┐ │                    │
                   │  │ Write deep results to  │ │                    │
                   │  │ Postgres (same trace)  │ │                    │
                   │  └────────────────────────┘ │                    │
                   └─────────────────────────────┘                    │
                                                                      │
┌─────────────────────────────────────────────────────────────────────┐
│                     NEXT.JS DASHBOARD                               │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Overview │  │ Traces   │  │ Trace    │  │ Eval     │           │
│  │ (metrics,│  │ List     │  │ Detail   │  │ Runs     │           │
│  │ failure  │  │ (search, │  │ (per-    │  │ (regres- │           │
│  │ mix,     │  │ filter,  │  │ stage    │  │ sion +   │           │
│  │ recovery │  │ project) │  │ eval,    │  │ experi-  │           │
│  │ insights)│  │          │  │ claims,  │  │ ment)    │           │
│  │          │  │          │  │ feedback)│  │          │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                     │
│  ┌──────────┐  ┌──────────┐                                        │
│  │ Docs +   │  │ Landing  │                                        │
│  │Playground│  │ Page     │                                        │
│  └──────────┘  └──────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Interactions

| Source | Target | Mechanism | Data |
|--------|--------|-----------|------|
| SDK → API | HTTP POST | `/v1/traces` | Full trace payload (query, chunks, answer, tokens) |
| SDK → API | HTTP POST | `/v1/traces?sync_deep_eval=true` | Trace + synchronous judge (recovery agent path) |
| SDK → API | HTTP POST | `/v1/eval/grade` | Question + expected + actual answer → correctness verdict |
| SDK → API | HTTP POST | `/v1/eval-runs` | Experiment results |
| SDK → API | HTTP GET | `/v1/traces/{id}` | Read back a trace (recovery polling) |
| API → Postgres | SQLAlchemy | JSONB insert/update | Full trace + indexed columns |
| API → Redis | redis-py | LPUSH/BRPOP | trace_id (UUID string) |
| API → OpenAI/Gemini | OpenAI SDK | `chat.completions.parse` / `embeddings.create` | Structured judge prompts / embedding texts |
| Worker → Postgres | SQLAlchemy | JSONB update | Deep eval results + re-diagnosis |
| Dashboard → API | fetch (no-store) | All GET endpoints | Traces, eval runs, job stats, projects |
| Dashboard → API | fetch | POST `/v1/playground` | Interactive demo query |
| Dashboard → API | fetch | POST `/v1/traces/{id}/feedback` | Thumbs up/down + comment |

## Request Flow (Trace Ingestion)

1. User's RAG app calls `client.trace()` or `client.log_trace()`
2. SDK sends HTTP POST to `/v1/traces` with the trace payload
3. API resolves API key → project_id (tenancy)
4. API computes cost from token counts + price table
5. API runs quick evaluation (embedding relevance + lexical groundedness + diagnosis)
6. API saves trace to Postgres (JSONB)
7. API enqueues deep eval: Redis LPUSH if available, else BackgroundTasks
8. API returns 202 with trace_id (+ diagnosis if `sync_deep_eval=true`)
9. Worker (or background task) runs LLM judge, re-diagnoses, updates Postgres

## Data Flow

```
SDK payload (dict) → Pydantic TraceIngestRequest → Quick Eval (mutates evaluations + diagnosis)
  → Cost Compute (mutates usage.cost_usd) → TraceRepository.save() → TraceRecord (JSONB)
  → Deep Eval Worker → LLM Judge → set_deep_evaluations() → Updated TraceRecord

Dashboard → fetch /v1/traces → TraceRecord.payload (raw JSONB) → api.ts mapper → MockTrace (UI type)
```

---

# PART 3 — COMPLETE FOLDER STRUCTURE

```
TraceroAI/
├── .env                          # Secrets (gitignored). Points at live Neon Postgres + Upstash Redis
├── .env.example                  # Template with all TRACEROAI_* env vars documented
├── .gitignore                    # Node, Python, secrets, scratch files
├── LICENSE                       # MIT, copyright 2026 chinmai-sd-123
├── README.md                     # Project README with architecture diagram, screenshots, quickstart
├── USAGE.md                      # Complete SDK usage guide (3 trace styles, recovery, experiments)
│
├── docs/
│   ├── traceroai-system-plan.md  # Full system design document (10 milestones, schemas, architecture)
│   ├── media/                    # Screenshots (dashboard.png, trace-detail.png, etc.)
│   └── reference-traces/         # Sample JSON traces for reference (gitignored in prod)
│
├── infra/
│   └── docker-compose.yml        # Local Postgres 16 + Redis 7 (dev only; prod uses Neon + Upstash)
│
├── services/
│   └── api/                      # Python FastAPI backend (the core platform)
│       ├── app/
│       │   ├── main.py           # FastAPI app creation, CORS, router mounting
│       │   ├── worker.py         # Redis BRPOP worker process for deep eval
│       │   ├── core/
│       │   │   ├── config.py     # Pydantic Settings (env vars, judge config, tenancy)
│       │   │   └── tenancy.py    # API key → project_id resolver
│       │   ├── db/
│       │   │   ├── base.py       # SQLAlchemy DeclarativeBase
│       │   │   ├── models.py     # TraceRecord + EvalRunRecord ORM models
│       │   │   ├── session.py    # Engine + SessionLocal factory
│       │   │   └── init_db.py    # create_all script
│       │   ├── api/routes/
│       │   │   ├── traces.py     # POST/GET traces, feedback, projects
│       │   │   ├── eval_runs.py  # POST/GET eval runs, projects
│       │   │   ├── eval_grade.py # POST /v1/eval/grade (correctness grading)
│       │   │   ├── health.py     # GET /health, /health/db
│       │   │   ├── jobs.py       # GET /v1/jobs/stats (queue health)
│       │   │   └── playground.py # POST /v1/playground (live demo RAG)
│       │   ├── schemas/
│       │   │   ├── traces.py     # Pydantic models for trace ingest/response
│       │   │   └── eval_runs.py  # Pydantic models for eval run ingest/response
│       │   ├── services/
│       │   │   ├── trace_repository.py    # Postgres CRUD for traces
│       │   │   ├── trace_store.py         # Legacy in-memory store (unused)
│       │   │   ├── eval_run_repository.py # Postgres CRUD for eval runs
│       │   │   ├── quick_evaluation.py    # Orchestrates embedding + lexical evaluators
│       │   │   ├── deep_evaluation.py     # Orchestrates LLM judge evaluators
│       │   │   ├── deep_eval_queue.py     # Redis queue (LPUSH/LLEN)
│       │   │   ├── llm_judge.py           # OpenAI SDK structured output judge
│       │   │   ├── embeddings.py          # Hosted embedding client + cosine similarity
│       │   │   ├── cost.py                # Token → USD computation (LiteLLM + fallback)
│       │   │   └── rate_limiter.py        # Redis fixed-window rate limiter
│       │   ├── evaluators/
│       │   │   ├── __init__.py
│       │   │   ├── groundedness.py        # Deterministic term-overlap groundedness
│       │   │   ├── context_relevance.py   # Embedding + lexical context relevance
│       │   │   ├── answer_relevance.py    # Embedding + lexical answer relevance
│       │   │   ├── deep_groundedness.py   # LLM judge claim-level groundedness
│       │   │   ├── deep_relevance.py      # LLM judge context + answer relevance
│       │   │   └── diagnosis.py           # 6-label diagnosis reducer + refusal detection
│       │   └── eval/
│       │       ├── __init__.py
│       │       ├── golden_traces.json     # 9 golden cases for regression testing
│       │       └── regression_gate.py     # Runs quick eval on golden set, reports accuracy
│       ├── tests/                         # 15 pytest files (integration + unit)
│       ├── clear_tables.py               # Ops utility to clear DB tables (gitignored)
│       ├── pyproject.toml                # Python project config
│       └── requirements.txt              # Render deployment deps
│
├── sdks/
│   └── python/                   # Published PyPI package: `pip install traceroai`
│       ├── traceroai/
│       │   ├── __init__.py       # Exports TraceroClient, TraceContext
│       │   ├── client.py         # HTTP client (trace, traced, log_trace, get_trace)
│       │   ├── trace.py          # TraceContext (context manager, auto-timing, best-effort)
│       │   ├── eval.py           # Experiment harness (run_experiment, Case, Variant)
│       │   └── recovery.py       # LangGraph RecoveryAgent (self-healing state machine)
│       ├── pyproject.toml        # v0.4.0, httpx dep, [recovery] optional extra
│       ├── README.md             # PyPI readme
│       ├── test_sdk_ergonomics.py # Context manager + decorator tests
│       ├── test_eval.py          # Experiment harness tests
│       ├── test_recovery.py      # Recovery agent tests
│       └── manual_smoke_send.py  # Manual smoke test (gitignored)
│
├── examples/
│   └── recovery-agent/           # Complete runnable example
│       ├── app.py                # Vector store RAG + recovery agent + experiment mode
│       ├── dataset.py            # 10 labeled eval cases
│       ├── requirements.txt      # traceroai[recovery], langchain, dotenv
│       ├── README.md             # Setup + usage docs
│       ├── .env.example          # Template
│       └── docs/                 # Knowledge base documents (4 files)
│
└── traceroai-web/                # Next.js 16 dashboard + marketing site
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx        # Root layout (fonts, SEO metadata, analytics)
    │   │   ├── page.tsx          # Landing page (hero, features, screenshots)
    │   │   ├── globals.css       # Tailwind v4 + dark theme
    │   │   ├── robots.ts         # SEO robots.txt
    │   │   ├── sitemap.ts        # SEO sitemap.xml
    │   │   ├── dashboard/
    │   │   │   ├── layout.tsx    # Dashboard shell (nav bar, container)
    │   │   │   ├── page.tsx      # Overview (metrics, failure mix, recovery insights)
    │   │   │   ├── nav.tsx       # Navigation tabs
    │   │   │   ├── loading.tsx   # Skeleton loader
    │   │   │   ├── skeleton.tsx  # Reusable skeleton components
    │   │   │   ├── error.tsx     # Error boundary
    │   │   │   ├── not-found.tsx # 404 page
    │   │   │   ├── traces/
    │   │   │   │   ├── page.tsx           # Trace list (server component)
    │   │   │   │   ├── trace-list.tsx     # Client: search, filter, table
    │   │   │   │   ├── project-selector.tsx # Client: project dropdown
    │   │   │   │   ├── loading.tsx        # Skeleton
    │   │   │   │   └── [traceId]/
    │   │   │   │       ├── page.tsx       # Trace detail (full inspection)
    │   │   │   │       └── feedback-widget.tsx # Client: thumbs up/down
    │   │   │   └── eval-runs/
    │   │   │       ├── page.tsx           # Eval runs list
    │   │   │       ├── loading.tsx        # Skeleton
    │   │   │       └── [evalRunId]/
    │   │   │           └── page.tsx       # Eval run detail
    │   │   └── docs/
    │   │       ├── page.tsx      # SDK docs with code examples
    │   │       ├── playground.tsx # Interactive "try it" widget
    │   │       ├── code-tabs.tsx  # Tabbed code blocks with copy
    │   │       └── section-nav.tsx # Sticky sidebar with scroll-spy
    │   └── lib/
    │       ├── api.ts            # API client (fetch, mappers, types)
    │       ├── mock-traces.ts    # MockTrace type + 3 reference traces
    │       └── mock-eval-runs.ts # EvalRun types + sample data
    ├── package.json              # Next.js 16, React 19, Tailwind v4
    ├── next.config.ts            # Empty (defaults)
    ├── tsconfig.json             # Strict, @/* path alias
    ├── CLAUDE.md / AGENTS.md     # AI agent instructions
    └── public/                   # Static assets (screenshots, SVGs)
```

---

# PART 4 — FILE-BY-FILE DEEP DIVE

*(Organized by subsystem for readability. Every file is covered.)*

## Backend Core

### `services/api/app/main.py`
**Purpose:** FastAPI application entry point.
**Imports:** All route routers (traces, health, eval_runs, jobs, playground, eval_grade), CORSMiddleware, config.
**Responsibilities:** Creates the `app` instance, configures CORS (localhost:3000 + settings.cors_origins), mounts all routers.
**Dependencies:** Incoming — uvicorn (startup). Outgoing — all route modules, config.
**Complexity:** Low. Pure wiring.

### `services/api/app/core/config.py`
**Purpose:** Centralized configuration from environment variables.
**Class `Settings`:** Pydantic BaseSettings with TRACEROAI_ prefix. Fields: database_url, openai_api_key, judge_model, embedding_model, judge_base_url, deep_eval_enabled, redis_url, project_api_keys (dict from JSON string), require_api_key, cors_origins (list from JSON string).
**Key detail:** `ENV_FILE` is anchored to `Path(__file__).resolve().parents[4] / ".env"` — this means config.py resolves the root `.env` regardless of CWD. The `judge_base_url` validator converts empty strings to None (OpenAI SDK treats `""` as a malformed URL).
**Caching:** `@lru_cache()` on `get_settings()` — singleton for process lifetime.

### `services/api/app/core/tenancy.py`
**Purpose:** Multi-tenant project resolution.
**Function `project_for_api_key(authorization)`:** Strips "Bearer " prefix, looks up the token in `settings.project_api_keys`, returns the project_id or None.
**Design:** Stateless lookup — no DB table for tenants. The key→project map lives in env vars.

## Backend Database

### `services/api/app/db/base.py`
**Purpose:** SQLAlchemy declarative base class.
**Content:** Single class `Base(DeclarativeBase)`.

### `services/api/app/db/models.py`
**Purpose:** ORM models for `traces` and `eval_runs` tables.
**`TraceRecord`:** Indexed columns (trace_id UUID PK, project_id, environment, status, diagnosis_label, model_name, total_latency_ms) + JSONB `payload` column containing the full trace. `created_at` with server default `func.now()`.
**`EvalRunRecord`:** Similar pattern — indexed metadata columns + JSONB `payload`. Includes dataset_id, pipeline_version, case counts.
**Design decision:** The JSONB `payload` stores the full Pydantic model as JSON. Indexed columns are denormalized for filtering. This avoids complex relational modeling while enabling efficient queries.

### `services/api/app/db/session.py`
**Purpose:** Engine and session factory.
**Engine:** `create_engine(settings.database_url, pool_pre_ping=True)` — pre-ping detects stale connections (important for Neon's connection recycling).
**`get_db()`:** Generator yielding a Session, used as a FastAPI Depends.

### `services/api/app/db/init_db.py`
**Purpose:** Table creation script. Imports models (to register them on Base.metadata), then `Base.metadata.create_all(bind=engine)`.

## Backend Schemas

### `services/api/app/schemas/traces.py`
**Purpose:** Pydantic models defining the complete trace schema.
**Key models:**
- `ProjectInfo`: project_id (default "demo-rag"), environment (default "dev")
- `QueryTrace`: original (required), rewritten, rewrite_changed, rewrite_method
- `RetrievedChunk`: rank, chunk_id, text (required), plus optional scoring fields (rrf_score, lexical_rank, dense_rank, lexical_score, dense_score)
- `GenerationTrace`: model (required), answer (required), answered (bool), usage (UsageTrace)
- `UsageTrace`: prompt_tokens, completion_tokens, total_tokens, cost_usd — cost is server-computed
- `EvaluationResult`: evaluator_name, evaluator_version, label, score [0,1], reason, details dict
- `EvaluationsTrace`: quick (list), deep (list) — two evaluation tiers
- `FeedbackEntry`: rating (thumbs_up/thumbs_down literal), comment, created_at
- `TraceIngestRequest`: Top-level model with all sub-models, defaults for schema_version, trace_id (uuid4), timestamp, status
- `TraceIngestResponse`: trace_id, status, message, optional diagnosis (for sync deep eval)

### `services/api/app/schemas/eval_runs.py`
**Purpose:** Pydantic models for eval run schema with comprehensive validation.
**Key validation (model_validator):**
- passed_cases + failed_cases must equal total_cases
- pass_rate must match the ratio
- Completed regression runs must have cases but no variants
- Completed experiments must have >= 2 variants but no cases
- Case counts must match summary

## Backend Routes

### `services/api/app/api/routes/traces.py`
**Purpose:** The central ingest + query API.
**Endpoints:**
- `POST /v1/traces` (202): Ingest. Resolves tenancy → computes cost → runs quick eval → saves → enqueues deep eval. Supports `?sync_deep_eval=true` for recovery agent.
- `GET /v1/traces` (200): List traces, optional `?project_id=` filter.
- `GET /v1/traces/projects` (200): Distinct project_ids.
- `GET /v1/traces/{trace_id}` (200/404): Single trace.
- `POST /v1/traces/{trace_id}/feedback` (201/404/422): Add feedback entry.

**Key flow in `ingest_trace`:**
1. `project_for_api_key(authorization)` → resolve project
2. If `require_api_key` and no project → 401
3. Compute `total_tokens` and `cost_usd`
4. `run_quick_evaluation(payload)` → mutates evaluations + diagnosis
5. `repository.save(payload)` → Postgres
6. If `sync_deep_eval`: run judge inline, return judge diagnosis
7. Else: enqueue to Redis or BackgroundTasks

### `services/api/app/api/routes/eval_runs.py`
**Purpose:** Eval run CRUD.
**Endpoints:**
- `POST /v1/eval-runs` (201/409/422): Create eval run. DuplicateEvalRunError → 409.
- `GET /v1/eval-runs` (200): List, optional `?project_id=`.
- `GET /v1/eval-runs/projects` (200): Distinct project_ids. Declared before `/{id}` to avoid path capture.
- `GET /v1/eval-runs/{eval_run_id}` (200/404): Single eval run.

### `services/api/app/api/routes/eval_grade.py`
**Purpose:** Single correctness-grading endpoint for the SDK eval harness.
**Endpoint:** `POST /v1/eval/grade` → `GradeResponse(correct, reason)`.
**Flow:** Creates an `OpenAIJudge`, calls `judge_answer_correctness(question, expected, actual)`. Returns 503 if no judge configured, 502 on provider errors.

### `services/api/app/api/routes/health.py`
**Purpose:** Health checks.
**Endpoints:** `GET /health` → `{"status": "ok"}`. `GET /health/db` → runs `SELECT 1` against Postgres.

### `services/api/app/api/routes/jobs.py`
**Purpose:** Queue health endpoint.
**Endpoint:** `GET /v1/jobs/stats` → `{"redis_connected": bool, "queued": int}`.

### `services/api/app/api/routes/playground.py`
**Purpose:** Public interactive demo endpoint.
**Endpoint:** `POST /v1/playground` → runs a minimal lexical RAG over 37 built-in FAQ documents, ingests as a real trace (evaluated + diagnosed), optionally runs LLM judge synchronously.
**Key details:**
- Rate-limited to 10 req/min per IP via `check_rate_limit`
- Extractive answer (no LLM needed for the base path)
- If judge is configured: runs deep eval synchronously for the flagship quick→deep correction demo
- Returns query, prompt, answer, chunks, diagnosis, and judged_by (deterministic or llm_judge)

## Backend Services

### `services/api/app/services/trace_repository.py`
**Purpose:** Repository pattern for Postgres trace CRUD.
**Methods:**
- `save(trace)`: Maps TraceIngestRequest to TraceRecord (denormalizes indexed fields), commits.
- `list(project_id=)`: SELECT ordered by created_at DESC, optional WHERE project_id.
- `list_projects()`: SELECT DISTINCT project_id.
- `get(trace_id)`: Primary key lookup.
- `set_deep_evaluations(trace_id, results, diagnosis=)`: Loads trace from JSONB, sets `evaluations.deep`, optionally overwrites diagnosis + `diagnosis_label` column, saves back.
- `add_feedback(trace_id, entry)`: Appends to `trace.feedback` list in JSONB.

### `services/api/app/services/trace_store.py`
**Purpose:** Legacy in-memory trace store. Simple `dict[UUID, TraceIngestRequest]`. **Not used in production** — superseded by TraceRepository.

### `services/api/app/services/eval_run_repository.py`
**Purpose:** Repository pattern for eval runs.
**Methods:** save (with IntegrityError → DuplicateEvalRunError), list (project_id filter), list_projects, get.

### `services/api/app/services/quick_evaluation.py`
**Purpose:** Orchestrates the synchronous quick evaluation pipeline.
**Flow:**
1. `_embed_relevance_inputs(trace)` — embeds [query, context, answer] in ONE batched API call, returns vectors dict
2. Runs context_relevance (with vectors), groundedness, answer_relevance (with vectors)
3. Sets `trace.evaluations.quick`
4. Detects refusal (`is_refusal`) and runs `diagnose_trace`
5. Sets `trace.diagnosis`

**Design insight:** The embedder is called ONCE for the query/context/answer triple, and the resulting vectors are shared with both relevance evaluators. This halves the embedding API calls per trace.

### `services/api/app/services/deep_evaluation.py`
**Purpose:** Asynchronous deep evaluation with the LLM judge.
**Flow:**
1. Opens its OWN `SessionLocal()` (not a FastAPI dependency — runs outside the request lifecycle)
2. Loads trace from Postgres
3. Runs 3 evaluators: deep_context_relevance, deep_groundedness, deep_answer_relevance
4. `diagnose_from_deep(results)` — maps judge verdicts to the quick eval vocabulary, re-diagnoses
5. `set_deep_evaluations(trace_id, results, diagnosis=)` — writes back to Postgres

**Error handling:** If the judge fails, returns a single `EvaluationResult(label="error")`. If `diagnose_from_deep` returns None, the quick diagnosis is kept.

### `services/api/app/services/deep_eval_queue.py`
**Purpose:** Redis queue abstraction.
**Functions:**
- `enqueue_deep_eval_request(trace_id)` → `LPUSH` to `traceroai:deep_eval` list. Returns False if Redis unavailable.
- `queue_stats()` → `{"redis_connected": bool, "queued": LLEN}`. Degrades gracefully.

### `services/api/app/services/llm_judge.py`
**Purpose:** LLM judge abstraction — the core AI evaluation engine.
**Protocol `LLMJudge`:** 4 methods — `judge_claim_groundedness`, `judge_context_relevance`, `judge_answer_relevance`, `judge_answer_correctness`.
**Class `OpenAIJudge`:** Uses `client.chat.completions.parse` with Pydantic models as `response_format` (structured output). Each method has a carefully crafted system prompt.
**Output models:** `JudgedClaim(claim, supported, reason)`, `ClaimGroundednessVerdict(claims[])`, `RelevanceVerdict(relevant, reason)`, `CorrectnessVerdict(correct, reason)`.
**Flexibility:** `base_url=settings.judge_base_url` — works with OpenAI or any compatible endpoint (Gemini, etc.).

### `services/api/app/services/embeddings.py`
**Purpose:** Hosted embedding client for quick evaluators.
**Class `EmbeddingClient`:** Uses OpenAI SDK `embeddings.create` with `settings.embedding_model`. Shares the judge's base_url/key config.
**Function `cosine_similarity(a, b)`:** Manual dot-product / norm computation, clamped to [0, 1].

### `services/api/app/services/cost.py`
**Purpose:** Server-side token → USD cost computation.
**Two-tier pricing:**
1. Primary: Fetches LiteLLM community pricing JSON (cached per-process, thread-safe with lock)
2. Fallback: Built-in `_PRICES` dict with OpenAI, Gemini, Claude model pricing
**Matching:** Exact name first, then longest-prefix (so `gpt-4o-mini-2024-07-18` matches `gpt-4o-mini`).
**Function `compute_cost_usd(model, usage)`:** Returns USD or None for unknown models — never fabricates.

### `services/api/app/services/rate_limiter.py`
**Purpose:** Redis-backed fixed-window rate limiter.
**Function `check_rate_limit(bucket, identity, limit, window_seconds)`:** INCR key, EXPIRE on first hit. Returns True if allowed. **Fails open** — if Redis unavailable, always allows.

## Backend Evaluators

### `services/api/app/evaluators/groundedness.py`
**Purpose:** Deterministic (lexical) groundedness evaluator.
**Algorithm:** Extract terms from answer and context (stopword removal + suffix normalization: -ies→-y, -ed, -es, -s with ss-guard). Compute intersection/answer ratio.
**Thresholds:** pass >= 0.75, needs_review >= 0.45, fail below.
**Known limitation:** Term-overlap can't detect semantic equivalence ("5-7 business days" vs "how long") or per-claim analysis (one fabricated claim in a long answer only dips the average).

### `services/api/app/evaluators/context_relevance.py`
**Purpose:** Dual-path context relevance evaluator.
**Primary path (embedding):** Cosine similarity of query vs context embeddings. Pass >= 0.45, review >= 0.30.
**Fallback path (lexical):** Term overlap. Pass >= 0.70, review >= 0.40.
**Accepts precomputed vectors** from the orchestrator to avoid redundant embedding calls.

### `services/api/app/evaluators/answer_relevance.py`
**Purpose:** Dual-path answer relevance evaluator. Same pattern as context_relevance but compares query vs answer.

### `services/api/app/evaluators/deep_groundedness.py`
**Purpose:** LLM-judge claim-level groundedness.
**Algorithm:** Sends answer + context to judge, receives per-claim supported/unsupported verdicts. Uses 80% threshold — if >= 80% of claims are supported, the answer is "grounded" (tolerates minor peripheral slips).

### `services/api/app/evaluators/deep_relevance.py`
**Purpose:** LLM-judge relevance evaluators.
**Functions:** `evaluate_deep_context_relevance` and `evaluate_deep_answer_relevance`. Both delegate to the judge and convert boolean verdicts to "relevant"/"irrelevant" labels.

### `services/api/app/evaluators/diagnosis.py`
**Purpose:** The diagnosis reducer — maps evaluation results to one of 6 labels.
**`is_refusal(answer)`:** Checks for phrases like "i don't know", "cannot answer", etc.
**`diagnose_trace(evaluations, refused=)`:** Priority-ordered reducer:
1. If refused + context relevant → `wrong_answer` (wrong refusal)
2. If refused + context not relevant → `correct_refusal`
3. If context_relevance == fail → `retrieval_miss`
4. If groundedness == fail → `unsupported_claim`
5. If answer_relevance == fail → `wrong_answer`
6. If all pass → `healthy_answer`
7. Else → `needs_review`

**`diagnose_from_deep(deep_evaluations, refused=)`:** Maps deep evaluator names/labels to the quick vocabulary, then delegates to `diagnose_trace`.

## Backend Eval

### `services/api/app/eval/regression_gate.py`
**Purpose:** Regression testing for the evaluation pipeline.
**Flow:** Loads golden traces from JSON, runs `run_quick_evaluation` on each, compares actual vs expected diagnosis, produces a `GateReport(results, accuracy, failures)`.

### `services/api/app/eval/golden_traces.json`
**Purpose:** 9 labeled golden cases: 4 healthy_answer, 3 unsupported_claim, 2 retrieval_miss.

## Backend Worker

### `services/api/app/worker.py`
**Purpose:** Standalone process consuming the Redis deep eval queue.
**Flow:** Connects to Redis, `brpop(QUEUE_NAME, timeout=2)` in a loop (bounded timeout < Redis's 5s socket timeout), calls `run_deep_evaluation(UUID(trace_id))` for each job. Handles connection errors with retry. Exits if no redis_url configured.

## SDK

### `sdks/python/traceroai/client.py`
**Purpose:** The main SDK client.
**Methods:**
- `trace(query)` → returns TraceContext (context manager)
- `traced(model=, strategy=)` → decorator for `(answer, chunks)` returning functions
- `log_trace(...)` → low-level dict-based trace send
- `log_trace_sync_eval(...)` → sends with `?sync_deep_eval=true`, returns (trace_id, diagnosis)
- `get_trace(trace_id)` → reads back a stored trace
**Auth:** Optional `api_key` → `Authorization: Bearer` header.

### `sdks/python/traceroai/trace.py`
**Purpose:** Context manager for ergonomic tracing.
**Class `TraceContext`:**
- `log_retrieval(chunks, strategy=, config=)` → builds retrieval dict
- `log_prompt(content, version=, template_name=)` → builds prompt dict
- `log_generation(answer, model=, prompt_tokens=, completion_tokens=)` → builds generation dict with optional token usage
- `__enter__` → starts timer
- `__exit__` → computes total_ms, sends via `client.log_trace()`, **best-effort** (try/except → warn, never raise)
- If exception in block: marks answered=False, inserts placeholder answer with error

### `sdks/python/traceroai/eval.py`
**Purpose:** Client-side experiment harness.
**Function `run_experiment(client, dataset, retrieve, generate, variants)`:**
1. For each variant: runs retrieve/generate per case, grades via `POST /v1/eval/grade`
2. Ungradeable cases (judge down) excluded from accuracy, never counted wrong
3. Winner: highest accuracy, tie-break on lower latency
4. Posts result to `POST /v1/eval-runs`

### `sdks/python/traceroai/recovery.py`
**Purpose:** Self-healing RAG recovery agent built on LangGraph.
**State machine:** `retrieve → generate → evaluate → (conditional edge)`
**Conditional routing (`_route`):**
- `healthy_answer` or `correct_refusal` → END (success)
- `attempt >= max_attempts` → END (give up)
- `retrieval_miss` → bump_retrieval (top_k += 2, rewrite query)
- `unsupported_claim` → tighten_generation (prompt_style="strict")
- `wrong_answer` → tighten first, then re-retrieve if that fails
- `needs_review` → re-retrieve

**Judge integration:** Uses `log_trace_sync_eval` for judge-quality routing (no async polling needed).
**Deep eval confirmation:** After the final answer, optionally polls for the async deep eval verdict.

## Frontend

### `traceroai-web/src/lib/api.ts`
**Purpose:** Central API client layer.
**Fetch functions:** `getTraces`, `getTrace`, `getEvalRuns`, `getEvalRun`, `getProjects`, `getEvalRunProjects`, `getJobStats`, `tryPlayground`. All use `cache: "no-store"`, return empty data on failure (honest empty states).
**Mapper functions:** `mapApiTraceToUiTrace` (snake_case → camelCase, maps deep eval results, detects eval methods, extracts recovery metadata), `mapApiEvalRunToRegressionRun`, `mapApiEvalRunToExperimentRun`.
**`normalizeDiagnosis`:** Whitelists known labels, maps unknown to "needs_review".

### `traceroai-web/src/lib/mock-traces.ts`
**Purpose:** Defines the `TraceDiagnosis` union type and `MockTrace` type used throughout the UI. Contains 3 hardcoded reference traces (used only as type reference; the fetchers return `[]` on failure, not mock data).

### `traceroai-web/src/lib/mock-eval-runs.ts`
**Purpose:** Defines `RegressionEvalRun` and `ExperimentEvalRun` types with sample data.

### Dashboard Pages

**`traceroai-web/src/app/dashboard/page.tsx`:** Overview page. Fetches traces, job stats, eval runs, projects in parallel. Computes healthy rate, avg/p95 latency (only over measured traces), cost, open failures. Renders metric cards, recent traces, eval methods mix, failure mix histogram, groundedness distribution, latest experiment, recovery insights.

**`traceroai-web/src/app/dashboard/traces/page.tsx`:** Trace list. Server component passing data to TraceList client component. Supports `?diagnosis=` for pre-filtered views from dashboard links.

**`traceroai-web/src/app/dashboard/traces/trace-list.tsx`:** Client component with text search, diagnosis filter chips, table with recovery badges, strategy, model, latency.

**`traceroai-web/src/app/dashboard/traces/[traceId]/page.tsx`:** Trace detail. Full inspection: query, answer, diagnosis badge, per-stage evaluations, deep LLM judge claims, generation params, retrieval config, prompt, chunks with scores, feedback.

**`traceroai-web/src/app/dashboard/traces/[traceId]/feedback-widget.tsx`:** Client component for thumbs up/down feedback submission.

**`traceroai-web/src/app/dashboard/eval-runs/page.tsx`:** Eval runs list with regression and experiment sections.

**`traceroai-web/src/app/dashboard/eval-runs/[evalRunId]/page.tsx`:** Eval run detail with metrics, cases/variants, recommendation.

**`traceroai-web/src/app/docs/page.tsx`:** Documentation page with SDK examples, diagnosis reference, recovery docs.

**`traceroai-web/src/app/docs/playground.tsx`:** Interactive playground calling the live API.

---

# PART 5 — EXECUTION FLOW

## Application Startup Sequence

### FastAPI Backend
1. **Python module import** — `app/main.py` is loaded
2. **Config loading** — `get_settings()` called (cached via lru_cache). Reads `.env` from repo root (anchored path). Validates `judge_base_url` (empty → None)
3. **Database engine creation** — `session.py` creates the SQLAlchemy engine with `pool_pre_ping=True`
4. **FastAPI app creation** — `FastAPI(title="TraceroAI API", version="0.1.0")`
5. **CORS middleware** — adds localhost:3000 + `settings.cors_origins`
6. **Router mounting** — health, traces, eval_runs, jobs, playground, eval_grade routers included
7. **Uvicorn serves** — `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Redis Worker (separate process)
1. **Config loading** — same `get_settings()`
2. **Redis connection** — `Redis.from_url(settings.redis_url)`
3. **BRPOP loop** — blocks on `traceroai:deep_eval` queue, timeout=2s
4. **On job:** calls `run_deep_evaluation(UUID(trace_id))`

### Next.js Dashboard
1. **`next dev` / `next build && next start`**
2. **Root layout** loads fonts (Geist, Geist Mono), SEO metadata, Vercel Analytics
3. **Server components** fetch data from `NEXT_PUBLIC_TRACEROAI_API_URL` (default 127.0.0.1:8000)
4. **On failure:** all fetchers return empty data → honest empty states (no mock data fallback)

---

# PART 6 — REQUEST LIFECYCLE

## POST /v1/traces (Trace Ingestion)

```
Client (SDK)
  │ HTTP POST /v1/traces
  │ Headers: Authorization: Bearer <api_key>  (optional)
  │ Body: TraceIngestRequest JSON
  ▼
FastAPI Route (traces.py:ingest_trace)
  │
  ├─ 1. Tenancy Resolution
  │    project_for_api_key(authorization)
  │    ├─ Known key → project_id (server-stamped, overrides client)
  │    ├─ Unknown/missing + require_api_key=True → 401 Unauthorized
  │    └─ Unknown/missing + require_api_key=False → keep client project
  │
  ├─ 2. Cost Computation
  │    compute_cost_usd(model, usage)
  │    ├─ total_tokens = prompt_tokens + completion_tokens
  │    ├─ price_for(model) → LiteLLM cache || built-in table
  │    └─ cost_usd = (prompt/1000)*in_price + (completion/1000)*out_price
  │
  ├─ 3. Quick Evaluation (SYNCHRONOUS)
  │    run_quick_evaluation(payload)
  │    ├─ _embed_relevance_inputs() → batch embed [query, context, answer]
  │    ├─ evaluate_context_relevance(trace, vectors=)
  │    │    ├─ Embedding path: cosine(query_vec, context_vec) → pass/review/fail
  │    │    └─ Lexical fallback: term overlap → pass/review/fail
  │    ├─ evaluate_groundedness(trace)
  │    │    └─ Term overlap: answer terms ∩ context terms → pass/review/fail
  │    ├─ evaluate_answer_relevance(trace, vectors=)
  │    │    ├─ Embedding path: cosine(query_vec, answer_vec) → pass/review/fail
  │    │    └─ Lexical fallback: term overlap → pass/review/fail
  │    └─ diagnose_trace(quick_results, refused=)
  │         └─ Priority reducer → one of 6 labels
  │
  ├─ 4. Save to Postgres
  │    TraceRepository(db).save(payload)
  │    └─ INSERT TraceRecord (denormalized indexed columns + JSONB payload)
  │
  ├─ 5. Deep Evaluation (ASYNCHRONOUS)
  │    ├─ sync_deep_eval=true: run_deep_evaluation(trace_id) INLINE
  │    │    └─ Returns judge-corrected diagnosis in response
  │    ├─ enqueue_deep_eval_request(trace_id) → Redis LPUSH
  │    │    └─ Returns True if Redis accepted
  │    └─ Fallback: background_tasks.add_task(run_deep_evaluation, trace_id)
  │
  └─ 6. Response
       TraceIngestResponse(trace_id=, status="accepted", diagnosis=)
       HTTP 202 Accepted
```

## Deep Evaluation (Worker/Background)

```
Worker (BRPOP) or BackgroundTask
  │
  ├─ 1. Open own DB session (SessionLocal)
  ├─ 2. Load trace from Postgres
  ├─ 3. Run LLM judge:
  │    ├─ evaluate_deep_context_relevance → judge.judge_context_relevance()
  │    ├─ evaluate_deep_groundedness → judge.judge_claim_groundedness()
  │    └─ evaluate_deep_answer_relevance → judge.judge_answer_relevance()
  ├─ 4. diagnose_from_deep(results, refused=)
  │    └─ Maps deep labels to quick vocabulary → diagnose_trace()
  └─ 5. set_deep_evaluations(trace_id, results, diagnosis=)
       └─ UPDATE TraceRecord: evaluations.deep + optional diagnosis overwrite
```

---

# PART 7 — DATABASE ANALYSIS

## Tables

### `traces`

| Column | Type | Indexed | Purpose |
|--------|------|---------|---------|
| trace_id | UUID (PK) | Yes | Primary identifier |
| schema_version | String | No | Schema versioning ("tracero_trace_v1") |
| project_id | String(100) | Yes | Multi-tenant filtering |
| environment | String(50) | Yes | dev/staging/production |
| status | String(50) | Yes | "answered" / other |
| query_text | String | No | Denormalized for potential search |
| diagnosis_label | String(100) | Yes | Denormalized for filtering |
| model_name | String(100) | No | Denormalized for analytics |
| total_latency_ms | Integer | No | Denormalized for analytics |
| payload | JSONB | No | **Full trace as JSON** |
| created_at | DateTime(tz) | No | Server timestamp |

### `eval_runs`

| Column | Type | Indexed | Purpose |
|--------|------|---------|---------|
| eval_run_id | UUID (PK) | Yes | Primary identifier |
| schema_version | String | No | Schema versioning |
| run_type | String(50) | Yes | "regression" / "experiment" |
| status | String(50) | Yes | "completed" / "failed" / etc. |
| project_id | String(100) | Yes | Multi-tenant filtering |
| environment | String(50) | Yes | Environment tag |
| dataset_id | String(100) | Yes | Dataset reference |
| dataset_name | String(200) | No | Human-readable name |
| dataset_version | String(100) | No | Dataset version |
| pipeline_version | String(100) | Yes | Pipeline version for filtering |
| baseline_pipeline_version | String(100) | No | Comparison baseline |
| total_cases | Integer | No | Case count |
| passed_cases | Integer | No | Pass count |
| failed_cases | Integer | No | Fail count |
| payload | JSONB | No | **Full eval run as JSON** |
| created_at | DateTime(tz) | No | Server timestamp |

## Schema Design Rationale

**JSONB + denormalized columns** is the core pattern. The full trace lives in JSONB (flexible, no migrations needed for new fields), while frequently-filtered fields are denormalized into indexed columns (project_id, diagnosis_label, status). This gives the flexibility of a document store with the query performance of a relational database.

## Query Patterns

- **List traces:** `SELECT * FROM traces WHERE project_id = ? ORDER BY created_at DESC`
- **Get trace:** `SELECT * FROM traces WHERE trace_id = ?` (PK lookup)
- **Distinct projects:** `SELECT DISTINCT project_id FROM traces ORDER BY project_id`
- **Deep eval update:** Load by PK → mutate JSONB → UPDATE (read-modify-write on the JSONB)

## Performance Concerns

- **JSONB read-modify-write:** `set_deep_evaluations` and `add_feedback` load the full JSONB, modify in Python, write back. Under high concurrency, this risks lost updates (no row-level locking beyond the transaction).
- **No pagination:** `list()` returns ALL traces for a project. Will degrade as trace count grows.
- **No connection pooling tuning:** Comment in session.py notes "Future: tune pool_size/max_overflow."

---

# PART 8 — BUSINESS LOGIC ANALYSIS

## Business Rules

### 1. Server owns evaluations and diagnosis
**Where:** `services/api/app/api/routes/traces.py`, `services/api/app/services/quick_evaluation.py`
**Rule:** Client-sent evaluations and diagnosis are ALWAYS overwritten by server-computed values. The server is the single source of truth.
**Edge case:** A sophisticated client that sends pre-computed evaluations will have them discarded silently.

### 2. Server owns cost
**Where:** `services/api/app/api/routes/traces.py`, `services/api/app/services/cost.py`
**Rule:** Cost is computed from the server's price table, not the client's. If a client sends `cost_usd`, it's accepted only if the server can't compute one (unknown model).
**Edge case:** Unknown models return `cost_usd=None` — never a fabricated number.

### 3. Deep eval overwrites quick diagnosis
**Where:** `services/api/app/services/deep_evaluation.py`, `services/api/app/services/trace_repository.py`
**Rule:** When the LLM judge produces a usable verdict, it overwrites the quick (deterministic) diagnosis. The judge is authoritative.
**Edge case:** If the judge errors, the quick diagnosis is preserved (not overwritten with an error).

### 4. Refusal detection and correct_refusal
**Where:** `services/api/app/evaluators/diagnosis.py`
**Rule:** A refusal ("I don't know") is `correct_refusal` only if the context genuinely lacked the answer. If the context was relevant but the model refused, it's `wrong_answer`.
**Edge case:** Empty answer strings are not considered refusals (checked by `not text`).

### 5. Reads stay open, writes gated
**Where:** `services/api/app/api/routes/traces.py`
**Rule:** When `require_api_key=True`, only `POST /v1/traces` requires authentication. All GET endpoints are unauthenticated — so recruiters/visitors can browse the dashboard freely.

### 6. Fail-open everywhere
**Where:** Multiple locations
**Rule:** Every external dependency degrades gracefully:
- Embeddings fail → lexical fallback
- Redis fail → BackgroundTasks fallback
- Judge fail → error EvaluationResult (not a crash)
- LiteLLM fetch fail → built-in price table
- Rate limiter Redis fail → allow the request
- SDK send fail → warn, don't raise

---

# PART 9 — AI/ML ANALYSIS

## Models Used

| Component | Model | Purpose | Provider |
|-----------|-------|---------|----------|
| Quick eval - relevance | `settings.embedding_model` (default `gemini-embedding-001`) | Cosine similarity for context/answer relevance | OpenAI-compatible API |
| Deep eval - judge | `settings.judge_model` (default `gpt-4o-mini`) | Claim-level groundedness, relevance, correctness grading | OpenAI-compatible API |
| Demo RAG generator | `extractive-demo` | Returns top chunk as answer (no LLM) | Built-in |
| Example app generator | `gpt-4o-mini` | Real LLM generation in the recovery example | OpenAI |

## Evaluation Pipeline

```
Trace Ingestion
  │
  ├─ QUICK EVAL (synchronous, every trace)
  │   ├─ Embedding Relevance (embedding_v1)
  │   │   └─ cosine_similarity(query_vec, context_vec) → pass/review/fail
  │   │   └─ cosine_similarity(query_vec, answer_vec) → pass/review/fail
  │   ├─ Lexical Groundedness (deterministic_v1)
  │   │   └─ term_overlap(answer_terms, context_terms) → pass/review/fail
  │   └─ Fallback: Lexical Relevance (deterministic_v1)
  │       └─ term_overlap(query_terms, context_terms) → pass/review/fail
  │
  └─ DEEP EVAL (asynchronous, LLM judge)
      ├─ Claim Groundedness (llm_judge_openai_v1)
      │   └─ Decomposes answer into atomic claims, judges each against context
      │   └─ 80% threshold: >= 80% supported → "grounded"
      ├─ Context Relevance (llm_judge_openai_v1)
      │   └─ Boolean: is context relevant to query?
      └─ Answer Relevance (llm_judge_openai_v1)
          └─ Boolean: does answer address query?
```

## Prompt Engineering

The judge uses carefully crafted system prompts (`services/api/app/services/llm_judge.py`):

- **Groundedness:** "Decompose the answer into atomic factual claims. For EACH claim decide if the CONTEXT directly supports it. Use ONLY the context. Never rely on outside knowledge."
- **Context relevance:** "Judge RETRIEVAL quality. Decide whether the context contains information that would help answer the query. Judge meaning and intent, not keyword overlap."
- **Answer relevance:** "Judge whether an ANSWER actually addresses a QUERY. A correct refusal when information is unavailable also counts as relevant."
- **Correctness:** "Grade a RAG ANSWER against a reference. If the expected answer is a refusal, then a refusal in the actual answer is correct."

## Structured Output

The judge uses OpenAI's structured output via `response_format=PydanticModel`. This ensures the response is always parseable — no regex extraction or JSON parsing errors.

## Recovery Agent (Self-Healing RAG)

The recovery agent (`sdks/python/traceroai/recovery.py`) is a LangGraph state machine:

```
START → retrieve → generate → evaluate → [conditional]
                                            │
                                ┌───────────┼───────────────┐
                                │           │               │
                          success (END)  fix_retrieval   fix_generation
                          give_up (END)      │               │
                                        bump_retrieval  tighten_generation
                                            │               │
                                        → retrieve      → generate
```

**Recovery actions:**
- `bump_retrieval`: top_k += 2, query rewrite with "(be specific and complete)"
- `tighten_generation`: prompt_style="strict", injects grounding instruction

## Measured Results

These numbers are **measured**, not estimated, and are reproducible from the repo:

```bash
cd services/api
.venv/Scripts/python.exe -m app.eval.benchmark          # accuracy + eval latency
.venv/Scripts/python.exe -m app.eval.cost_benchmark     # per-trace eval cost
```

Both run against the 9-case labeled golden set (`app/eval/golden_traces.json`):
4 `healthy_answer`, 3 `unsupported_claim`, 2 `retrieval_miss`.

### Diagnosis accuracy vs ground truth

| Layer | Result | Notes |
|-------|--------|-------|
| Deterministic quick eval | **8/9** | The single miss is a term-overlap blind spot: an answer that fabricates "quantum cryptography encryption" on top of a correct fact is labeled `needs_review` rather than `unsupported_claim`, because lexical overlap can't isolate the unsupported clause. |
| LLM judge (deep eval) | **9/9** | The judge closes that gap — per-claim decomposition flags the fabricated clause the lexical scorer misses. |

**Honest reading — do NOT report this as "the judge is 100% accurate."** It is *9/9 on a 9-case set*, which is a directional signal, not a calibrated accuracy. With n=9 the confidence interval is very wide, and the cases are deliberately clean (unambiguous fabrications and retrieval misses). A production-scale judge benchmark against human labels would be expected to land in the **80–90%** range, consistent with published RAG-judge frameworks (RAGAS, etc.). LLM judges are also non-deterministic — the same case can flip between runs. The result demonstrates that the judge **fixes the deterministic layer's known semantic-equivalence blind spot**, not that it is infallible.

### Eval-path latency (synchronous quick eval)

Measured over 180 samples (20 replays × 9 cases), embedding API round-trip included:

| p50 | p95 | mean | max |
|-----|-----|------|-----|
| ~1053 ms | ~1566 ms | ~1133 ms | ~3455 ms |

Latency is **dominated by the embedding API round-trip**, not local compute. The lexical fallback path (no embeddings) is sub-millisecond.

### Per-trace eval cost

Measured token usage from live embedding + judge calls, priced via `app/services/cost.py`:

| Stage | Per trace |
|-------|-----------|
| Quick eval (embeddings) | ~$0.000001 |
| Deep eval (LLM judge, 3 calls) | ~$0.000302 |
| **Total eval / trace** | **~$0.0003** (≈ $0.30 per 1,000 traces) |

The LLM judge is ~300× the cost of the embedding pass but still negligible in absolute terms. This is the cost/accuracy tradeoff the two-tier design is built on: the near-free deterministic pass runs on every trace; the $0.0003 judge runs to close the gap. **Caveat:** these figures are on short FAQ-style cases (~780 judge tokens/trace). Real traces with long context (e.g. large code chunks) cost proportionally more — the per-token pricing is exact, but the absolute number scales with context size. Generation (answer-LLM) cost is tracked separately per trace by the ingest path and is not included here.

---

# PART 10 — DEPENDENCY GRAPH

## Module Dependencies

```
main.py
  → routes/traces.py
  │   → core/config.py, core/tenancy.py
  │   → services/cost.py → schemas/traces.py, core/config.py
  │   → services/quick_evaluation.py
  │   │   → evaluators/context_relevance.py → evaluators/groundedness.py, services/embeddings.py
  │   │   → evaluators/answer_relevance.py → evaluators/groundedness.py, services/embeddings.py
  │   │   → evaluators/groundedness.py → schemas/traces.py
  │   │   → evaluators/diagnosis.py → schemas/traces.py
  │   │   → services/embeddings.py → core/config.py
  │   → services/deep_evaluation.py
  │   │   → evaluators/deep_groundedness.py → services/llm_judge.py
  │   │   → evaluators/deep_relevance.py → services/llm_judge.py
  │   │   → evaluators/diagnosis.py
  │   │   → services/llm_judge.py → core/config.py
  │   │   → services/trace_repository.py → db/models.py, schemas/traces.py
  │   │   → db/session.py → core/config.py, db/base.py
  │   → services/deep_eval_queue.py → core/config.py
  │   → services/trace_repository.py
  │
  → routes/eval_runs.py → services/eval_run_repository.py → db/models.py, schemas/eval_runs.py
  → routes/eval_grade.py → services/llm_judge.py, core/config.py
  → routes/health.py → db/session.py
  → routes/jobs.py → services/deep_eval_queue.py
  → routes/playground.py → services/quick_evaluation.py, services/llm_judge.py,
  │                         evaluators/deep_*, services/trace_repository.py,
  │                         services/rate_limiter.py
  │
  → core/config.py (root dependency — everything depends on settings)
```

## Coupling Analysis

**High cohesion:** The evaluator package is well-cohesive — each evaluator is a single function with a clear interface (`TraceIngestRequest → EvaluationResult`).

**Low coupling:** The `LLMJudge` Protocol decouples the evaluators from the OpenAI SDK — tests inject a `StubJudge`.

**Circular dependencies:** None detected. The dependency graph is a DAG.

**Tight coupling concern:** `quick_evaluation.py` imports all 3 quick evaluators and the diagnosis module directly. If the evaluator set changes, this orchestrator must be updated.

---

# PART 11 — DESIGN PATTERNS

## Repository Pattern
**Where:** `services/api/app/services/trace_repository.py`, `services/api/app/services/eval_run_repository.py`
**Usage:** Abstracts database access behind a class interface. Routes inject a `Session` via FastAPI Depends, create a Repository, and call methods.

## Protocol / Strategy Pattern
**Where:** `services/api/app/services/llm_judge.py`
**Usage:** `LLMJudge` is a `typing.Protocol` with 4 methods. `OpenAIJudge` implements it. Tests inject a `StubJudge`. The evaluators accept `LLMJudge` — they don't know which implementation they're using.

## Dependency Injection
**Where:** Recovery agent (`retrieve`/`generate` callables), evaluators (`embedder` parameter), SDK eval harness (`retrieve`/`generate` functions)
**Usage:** User-provided functions are injected into framework code. The platform owns the orchestration; the user owns the RAG pipeline.

## Observer / Event-Driven
**Where:** Redis queue + worker
**Usage:** Trace ingestion produces a "deep eval needed" event (LPUSH). The worker consumes events (BRPOP). Decouples the fast ingest path from the slow LLM judge.

## Fail-Open / Circuit Breaker (informal)
**Where:** Every external call
**Usage:** Every external dependency (Redis, embeddings, judge, LiteLLM pricing, rate limiter) wraps its call in try/except and falls back to a degraded-but-functional path. Not a formal circuit breaker, but the same principle.

## State Machine (LangGraph)
**Where:** `sdks/python/traceroai/recovery.py`
**Usage:** The recovery agent is a `StateGraph` with nodes (retrieve, generate, evaluate, bump_retrieval, tighten_generation) and conditional edges based on the diagnosis label.

## Mapper / Anti-Corruption Layer
**Where:** `traceroai-web/src/lib/api.ts` `mapApiTraceToUiTrace`
**Usage:** Translates the API's snake_case schema to the frontend's camelCase types. Normalizes unknown diagnosis labels to "needs_review".

---

# PART 12 — SECURITY REVIEW

## Authentication
- **API key authentication** via `Authorization: Bearer <key>` header
- Keys are stored as a JSON dict in env var `TRACEROAI_PROJECT_API_KEYS`
- `require_api_key` flag gates writes only; reads are always open
- **No user-level auth** — there are no user accounts, sessions, or JWTs

## Authorization
- **Write gating only:** POST /v1/traces requires a valid key when `require_api_key=True`
- **Reads ungated:** GET endpoints are open by design (dashboard is public)
- **No role-based access:** Any valid key can write to any project (the key determines the project)
- **Vulnerability:** `GET /v1/traces?project_id=<any>` accepts any project_id — an SDK user can read other projects' traces. Known limitation documented in roadmap.

## Secrets Handling
- **OpenAI/Gemini keys** are server-only (in `.env` / Render env vars). Never exposed to SDK or browser.
- **`NEXT_PUBLIC_*`** vars are browser-visible — only URLs, no secrets.
- **.env is gitignored.** `.env.example` has placeholder values.
- **PyPI token** used for publishing (stored separately, not in repo).

## Input Validation
- **Pydantic validation** on all ingest requests (field types, min_length, ge/le constraints)
- **Eval run model_validator** checks summary consistency
- **FeedbackEntry** uses `Literal["thumbs_up", "thumbs_down"]` — invalid ratings → 422
- **Playground** rate-limited to 10 req/min per IP

## Potential Vulnerabilities
1. **No SQL injection risk** — uses SQLAlchemy ORM, no raw string interpolation (except `clear_tables.py` which whitelists table names)
2. **No XSS risk** — Next.js escapes by default; `dangerouslySetInnerHTML` used only for JSON-LD (static content)
3. **CORS is configurable** but defaults to localhost — must be set for production
4. **Rate limiter fails open** — if Redis is down, no rate limiting. Under extreme load, the playground could be abused.
5. **No CSRF protection** — the feedback endpoint accepts POSTs without CSRF tokens (acceptable since there's no auth session to hijack)

---

# PART 13 — PERFORMANCE REVIEW

## Potential Issues

### 1. No Pagination
**Location:** `TraceRepository.list()`, `EvalRunRepository.list()`
**Impact:** Returns ALL records. With thousands of traces, this will cause memory pressure and slow responses.
**Fix:** Add `LIMIT/OFFSET` or cursor-based pagination.

### 2. JSONB Read-Modify-Write
**Location:** `set_deep_evaluations()`, `add_feedback()`
**Impact:** Full JSONB is loaded, deserialized to Pydantic, modified, serialized back, and written. Under concurrent deep eval writes, this could cause lost updates.
**Fix:** Use Postgres JSONB operators (`jsonb_set`) for targeted updates, or add explicit row locking.

### 3. Synchronous Embedding on Ingest Path
**Location:** `quick_evaluation.py:_embed_relevance_inputs()`
**Impact:** Every trace ingestion makes an HTTP call to the embedding API. If the API is slow, it blocks the response.
**Mitigation:** Already partially mitigated — batch embeds query+context+answer in one call. Falls back to lexical if it fails.

### 4. LiteLLM Pricing Fetch
**Location:** `cost.py:_load_litellm_prices()`
**Impact:** First trace ingestion fetches a ~1MB JSON file from GitHub. Cached for process lifetime, but cold start is slow.
**Mitigation:** Thread-safe lock prevents thundering herd. Falls back to built-in prices on failure.

### 5. Free-Tier Cold Starts
**Location:** Render deployment
**Impact:** Free tier sleeps after idle. First request takes 30-50s. Worker sleeps with it.
**Mitigation:** Dashboard shows loading skeletons. Playground shows "waking up" message.

### 6. Single Worker Process
**Location:** Colocated worker in Render start command
**Impact:** Worker runs as a background process in the same dyno. If it crashes, only Render's process manager (watching uvicorn) can restart it.
**Fix:** Separate worker dyno or use a proper process manager (supervisord).

---

# PART 14 — DEVOPS REVIEW

## Docker
**File:** `infra/docker-compose.yml`
- Postgres 16 Alpine with healthcheck (`pg_isready`)
- Redis 7 Alpine with healthcheck (`redis-cli ping`)
- Persistent volume for Postgres data
- **Local dev only** — production uses Neon + Upstash

## Deployment

### Backend (Render)
- **Service:** Web Service, free tier, Singapore region
- **Root dir:** `services/api`
- **Build:** `pip install -r requirements.txt`
- **Start:** `sh -c "python -m app.worker & uvicorn app.main:app --host 0.0.0.0 --port $PORT"` — worker backgrounded + uvicorn foreground in one dyno
- **Health check:** `/health`

### Frontend (Vercel)
- **Framework:** Next.js (auto-detected)
- **Domains:** `www.traceroai.tech` + `tracero-ai.vercel.app`
- **Env:** `NEXT_PUBLIC_TRACEROAI_API_URL` → Render URL (baked at build time)

### Database (Neon)
- Managed Postgres with connection recycling
- URL must use `postgresql+psycopg://` driver prefix
- Requires `sslmode=require`, no `channel_binding=require`

### Redis (Upstash)
- Managed Redis with TLS (`rediss://`)
- Used for deep eval queue + rate limiter

## CI/CD
**Status: NOT IMPLEMENTED.** No `.github/workflows/` directory. No CI pipeline. Tests run locally only.

## Monitoring
- `/health` endpoint for basic availability
- `/health/db` for database connectivity
- `/v1/jobs/stats` for Redis queue health
- Vercel Analytics for frontend
- **No APM, no alerting, no structured logging**

---

# PART 15 — TECHNICAL DEBT REVIEW

### Critical

1. **No pagination on list endpoints** — will break at scale. Both trace and eval run list endpoints return all records.

2. **No CI/CD** — tests run locally only. No automated checks on PR, no deployment pipeline. Risk of regressions going unnoticed.

3. **Legacy `trace_store.py`** — in-memory store is unused but still in the codebase. Dead code.

### High

4. **JSONB read-modify-write** for deep eval and feedback — potential lost updates under concurrency.

5. **No request/response logging** — no structured logging anywhere in the backend. Debugging production issues requires reading Render logs.

6. **Colocated worker** — runs as a backgrounded shell process. No auto-restart, no separate scaling.

7. **Read endpoints ungated** — any visitor can see any project's traces. Fine for a demo, not for production multi-tenancy.

### Medium

8. **Hardcoded playground KB** — 37 documents are inline in `playground.py`. Should be a data file.

9. **No database migrations** — uses `create_all` (DDL from models). Schema changes require manual migration or table recreation.

10. **`clear_tables.py` not truly gitignored** — listed in `.gitignore` but still appears in the file tree. Should be verified.

11. **test_deep_groundedness.py has duplicate StubJudge class** — defined twice in the same file (both identical).

### Low

12. **No type-checking in CI** — `mypy` or `pyright` not configured for the backend.

13. **`trace_store.py` import dead code** — should be deleted entirely.

14. **`next-env.d.ts` in gitignore but also in source** — Next.js auto-generates this; safe but noisy.

---

# PART 16 — IMPROVEMENT ROADMAP

## Quick Wins (Low effort, High impact)

| Improvement | Effort | Impact | Risk |
|-------------|--------|--------|------|
| Add pagination to list endpoints (LIMIT/OFFSET) | 2h | High — prevents scaling breakage | Low |
| Delete `trace_store.py` | 5min | Low — removes dead code | None |
| Fix duplicate StubJudge in test file | 5min | Low — cleaner tests | None |
| Add basic structured logging (Python `logging`) | 2h | Medium — production debugging | Low |
| Move playground KB to a JSON data file | 1h | Low — cleaner code | Low |

## Medium Improvements (Medium effort, Medium-High impact)

| Improvement | Effort | Impact | Risk |
|-------------|--------|--------|------|
| Add CI with GitHub Actions (pytest + tsc) | 4h | High — catches regressions | Low |
| Add Alembic for database migrations | 4h | High — safe schema evolution | Medium |
| Use Postgres JSONB operators for deep eval writes | 3h | Medium — eliminates lost updates | Medium |
| Separate worker dyno on Render | 2h | Medium — worker resilience | Low |
| Add cursor-based pagination | 4h | High — scales to large datasets | Low |

## Major Refactors (High effort, High impact)

| Improvement | Effort | Impact | Risk |
|-------------|--------|--------|------|
| User authentication + project-scoped reads | 2-3d | High — production multi-tenancy | Medium |
| OpenTelemetry integration | 3-5d | Medium — industry-standard observability | Medium |
| Async FastAPI with SQLAlchemy async | 3-5d | Medium — better concurrency | High |
| Proper background job framework (Celery/ARQ) | 2-3d | Medium — job reliability | Medium |

## Future Scaling Work

| Improvement | Effort | Impact | Risk |
|-------------|--------|--------|------|
| Multi-judge ensemble (A/B/C judges + aggregation) | 1w | Medium — reduces evaluator bias | Medium |
| ClickHouse for analytics queries | 1-2w | High — fast aggregations at scale | High |
| Object storage for large payloads | 1w | Medium — reduces Postgres payload size | Medium |
| Horizontal worker scaling | 3d | Medium — process more traces | Low |

---

# PART 17 — LEARNING MODE

## Module: Evaluation Pipeline

### Why it exists
RAG systems produce failures at different stages. A hallucinated answer could be caused by bad retrieval, good retrieval but bad generation, or the model ignoring good context. Without per-stage evaluation, you can't fix the right thing.

### Why designed this way
**Two-tier evaluation (quick + deep)** is the key architectural insight:
- **Quick** (embedding + lexical) runs synchronously on every trace — it's cheap and fast, providing an immediate diagnosis
- **Deep** (LLM judge) runs asynchronously — it's expensive but catches what lexical analysis misses (semantic equivalence, per-claim groundedness)

The quick eval diagnosis is the "first opinion"; the deep eval overwrites it when it lands — like a nurse's triage followed by a doctor's diagnosis.

### Alternatives considered
1. **LLM-only evaluation** — too expensive for every trace, too slow for the ingest path
2. **Lexical-only evaluation** — proven brittle (can't see "5-7 business days" answers "how long")
3. **Client-side evaluation** — breaks the "server owns truth" principle, splits the grading authority

### Tradeoffs
- The embedding path adds an API call to the ingest path (latency cost for accuracy gain)
- The 80% threshold on deep groundedness is permissive — it tolerates minor peripheral claims to avoid over-penalizing long answers
- The lexical fallback ensures ingest NEVER breaks, but produces lower-quality diagnoses

### Industry practices
This two-tier pattern mirrors how production ML eval systems work: fast heuristics for every prediction, expensive LLM-based evaluation for a sample or on-demand. Similar to RAGAS (open-source RAG eval framework) but with the quick/deep split and the self-healing recovery layer.

### Interview questions
1. "Why not just use the LLM judge for everything?" — Cost and latency. At scale, you can't afford an LLM call per trace on the synchronous ingest path.
2. "How would you handle the case where the quick and deep evaluations disagree?" — The deep eval ALWAYS wins. The architecture is designed for this: deep_evaluation.py overwrites the quick diagnosis.
3. "What happens if the LLM judge hallucinates its own verdict?" — The structured output constraint (Pydantic response_format) prevents parsing errors. A wrong verdict is still possible, but per-claim decomposition makes it verifiable.

## Module: Recovery Agent

### Why it exists
Most RAG failures are recoverable. A retrieval miss can be fixed by retrieving more documents. An unsupported claim can be fixed by regenerating with a stricter prompt. The recovery agent automates these retries.

### Why designed this way
**LangGraph state machine** was chosen because recovery is inherently stateful — you need to track attempts, which lever was pulled, and whether to escalate. A state machine makes the retry logic explicit and bounded (max_attempts prevents infinite loops).

**Dependency injection** (retrieve/generate callables) was chosen because the platform shouldn't own the user's RAG pipeline. The same pattern as the LLMJudge Protocol — the framework provides the orchestration, the user provides the implementation.

### Alternatives
1. **Simple retry loop** — doesn't capture which stage failed or which lever to pull
2. **Agent framework (LangChain agents)** — too opaque; the recovery logic should be explicit and inspectable
3. **Server-side recovery** — would require the server to know how to retrieve/generate, violating the platform/pipeline separation

### Tradeoffs
- Uses `sync_deep_eval` for judge-quality routing — adds ~3-5s per attempt for the LLM call, but avoids misrouting on the brittle quick eval
- `bump_retrieval` only adds +2 to top_k — conservative; for small KBs, k=1 still finds answers, so it may not actually trigger a retry
- Query rewrite is simplistic ("(be specific and complete)") — a real system would use an LLM for query expansion

---

# PART 18 — ENGINEERING HANDBOOK

## Architecture Summary

TraceroAI is a **three-component system**: Python SDK (pip install traceroai) → FastAPI backend (services/api) → Next.js dashboard (traceroai-web). Data flows unidirectionally: SDK → API → Postgres → Dashboard. Async deep evaluation is offloaded to a Redis queue + worker.

## Key Flows

1. **Trace ingestion:** SDK POST → tenancy → cost → quick eval → save → deep eval (async)
2. **Deep evaluation:** Worker/background → LLM judge → re-diagnosis → update Postgres
3. **Recovery:** SDK state machine → trace + sync judge → route on diagnosis → retry failed stage
4. **Experiment:** SDK harness → run variants → grade via server → post results → dashboard

## Important Files

| File | Why it matters |
|------|---------------|
| `services/api/app/api/routes/traces.py` | Central ingest route — all trace data flows through here |
| `services/api/app/evaluators/diagnosis.py` | The diagnosis reducer — the core business logic |
| `services/api/app/services/llm_judge.py` | The LLM judge — the most sophisticated AI component |
| `services/api/app/services/quick_evaluation.py` | Orchestrates the sync evaluation pipeline |
| `sdks/python/traceroai/recovery.py` | The LangGraph recovery agent — the flagship feature |
| `traceroai-web/src/lib/api.ts` | All frontend-backend communication |
| `services/api/app/core/config.py` | All configuration — the first place to look for "how do I change X" |

## Common Debugging Points

1. **Traces show "needs_review" when they should be healthy:** Check if embedding API is configured (`TRACEROAI_OPENAI_API_KEY` + `TRACEROAI_EMBEDDING_MODEL`). Without it, lexical fallback is brittle.
2. **Deep eval always shows "error":** Check `TRACEROAI_JUDGE_MODEL` and `TRACEROAI_JUDGE_BASE_URL`. An empty string base URL crashes the OpenAI SDK.
3. **Dashboard shows empty data:** Check `NEXT_PUBLIC_TRACEROAI_API_URL` — it's baked at build time. Must be set before `next build`.
4. **Cost shows as null:** Unknown model in the price table. Add it to `_PRICES` in cost.py or wait for LiteLLM cache refresh.
5. **Worker crashes after 5s idle:** Redis-py 8.0 default socket timeout. Fixed by using `brpop(timeout=2)` (under the 5s socket timeout).

## Production Risks

1. **No pagination** — API will degrade with thousands of traces
2. **Colocated worker** — if worker crashes, no auto-restart
3. **Single DB** — `.env` points at the LIVE Neon production DB. Local scripts hit prod.
4. **Free-tier cold starts** — 30-50s delay on first request after idle
5. **No CI** — regressions can reach production unchecked

## Maintenance Guide

**Adding a new evaluator:**
1. Create `evaluators/new_evaluator.py` with function `evaluate_X(trace: TraceIngestRequest) -> EvaluationResult`
2. Add to `quick_evaluation.py:run_quick_evaluation` (for quick) or `deep_evaluation.py:DEEP_EVALUATORS` (for deep)
3. Update `diagnosis.py:diagnose_trace` if it should affect diagnosis
4. Add test in `tests/test_new_evaluator.py`

**Adding a new diagnosis label:**
1. Add to `diagnosis.py:diagnose_trace`
2. Add to `traceroai-web/src/lib/mock-traces.ts:TraceDiagnosis` type
3. Add to `normalizeDiagnosis` whitelist in `api.ts`
4. Add styles to `diagnosisStyles` in `trace-list.tsx` and `[traceId]/page.tsx`

**Deploying a schema change:**
1. Add field to Pydantic model in `schemas/traces.py` (with a default for backwards compatibility)
2. If a new indexed column is needed: add to `db/models.py`, run `init_db.py` (or add Alembic migration)
3. Update `trace_repository.py:save` to populate the new column

**Running tests:**
```bash
cd services/api
python -m pytest tests/ -v        # Backend (needs live Postgres)
cd ../../sdks/python
python -m pytest -v               # SDK (no external deps)
cd ../../traceroai-web
npx tsc --noEmit                  # Frontend type checking
```
