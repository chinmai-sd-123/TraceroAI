<div align="center">

# TraceroAI

**RAG observability, evaluation, and debugging — built like production infrastructure.**

When a RAG answer is wrong, TraceroAI shows *why*: whether the failure came from
retrieval, the context, grounding, or the generated answer.

[![PyPI](https://img.shields.io/pypi/v/traceroai?color=06b6d4&label=pip%20install%20traceroai)](https://pypi.org/project/traceroai/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

**[Live demo →](https://www.traceroai.tech)** &nbsp;·&nbsp;
**[Interactive docs →](https://www.traceroai.tech/docs)** &nbsp;·&nbsp;
**[PyPI →](https://pypi.org/project/traceroai/)**

</div>

![TraceroAI — debug RAG failures before they reach users](docs/media/landing-hero.png)

---

## The problem

A bad RAG answer is only a *symptom*. The real cause could be anywhere in the pipeline:

```
user query → retrieval → context selection → prompt → generation → answer
```

Teams ship RAG systems with almost no visibility into *which stage* failed. Was the
right document never retrieved? Was it retrieved but ignored? Did the model
hallucinate beyond its context? "The answer is wrong" doesn't tell you where to look.

**TraceroAI traces every RAG answer and diagnoses the failure stage**, so debugging
becomes a lookup instead of a guess.

## What it does

- **Trace every answer** — capture the query, retrieved chunks, prompt, generated
  answer, and latency as one timeline.
- **Two-tier evaluation** — fast **embedding-based** semantic checks on every trace
  (context/answer relevance via cosine similarity), plus an optional **LLM-as-judge**
  for claim-level groundedness the cheap checks can't reason about.
- **Automatic diagnosis** — each trace is labeled with one of six outcomes:

  | Diagnosis | Meaning |
  |---|---|
  | `healthy_answer` | retrieval, grounding, and relevance all pass |
  | `correct_refusal` | model correctly declined when context didn't support an answer |
  | `retrieval_miss` | retrieved context doesn't match the query |
  | `unsupported_claim` | answer asserts things the context doesn't support |
  | `wrong_answer` | answer doesn't address the query |
  | `needs_review` | mixed signals — flagged for a human |

- **Drop-in SDK** — `pip install traceroai`; instrument any RAG pipeline in a few lines.
- **Self-healing recovery** (`pip install traceroai[recovery]`) — a LangGraph agent that
  retries the stage TraceroAI diagnoses as broken: a retrieval miss re-retrieves with
  more context, an unsupported claim re-generates with a stricter prompt, and it escalates
  to human review after a bounded number of attempts. Every attempt is traced.
- **Multi-tenant ingest** — project API keys attribute traces to a project; reads stay
  open so a recruiter can explore the demo without a key.

See **[USAGE.md](USAGE.md)** for a complete guide to every SDK feature.

## Architecture

TraceroAI separates the **write path** (fast, synchronous, must never block the caller)
from the **evaluation path** (slow, costly, rate-limited). Ingest returns in
milliseconds; expensive LLM judgement happens asynchronously and is reconciled back
onto the trace.

```mermaid
flowchart TB
    subgraph client["Your RAG application"]
        SDK["traceroai SDK<br/>context-manager · decorator · low-level"]
    end

    subgraph api["API service (FastAPI on Render)"]
        INGEST["POST /v1/traces<br/>auth · validate · stamp project"]
        QUICK["Quick evaluators<br/>(deterministic, &lt;5ms)<br/>context · groundedness · relevance"]
        DIAG["Diagnosis reducer<br/>→ one of 6 labels"]
        WORKER["Worker<br/>(colocated process)"]
        DEEP["Deep evaluators<br/>LLM-as-judge"]
        JUDGE{{"LLMJudge interface<br/>OpenAI · Gemini (swappable)"}}
    end

    PG[("Postgres / Neon<br/>traces as JSONB")]
    REDIS[["Redis / Upstash<br/>deep-eval queue"]]
    WEB["Next.js dashboard + docs<br/>(Vercel)"]

    SDK -->|"HTTPS"| INGEST
    INGEST --> QUICK --> DIAG
    DIAG -->|"persist + 202 Accepted"| PG
    INGEST -.->|"enqueue trace_id"| REDIS

    REDIS -.->|"dequeue"| WORKER
    WORKER --> DEEP --> JUDGE
    JUDGE -.->|"LLM API"| EXT(["OpenAI / Gemini"])
    DEEP -->|"reconcile verdicts"| PG

    WEB -->|"read traces / metrics"| PG
```

> Solid arrows are the synchronous request path; dotted arrows are the asynchronous
> evaluation path.

### Request lifecycle

1. The SDK sends a trace (query, retrieved chunks, prompt, answer) to `POST /v1/traces`.
2. The API authenticates the project key, runs the **deterministic quick evaluators**,
   computes a **diagnosis**, persists the trace, and returns **`202 Accepted`** — the
   caller is never blocked on evaluation.
3. The trace id is pushed onto a **Redis queue**.
4. A **worker** dequeues it and runs the **LLM-as-judge** deep evaluators, then
   reconciles the richer verdicts back onto the stored trace.
5. The **dashboard** reads traces and aggregate metrics for inspection.

### Design decisions & trade-offs

| Decision | Why | Trade-off accepted |
|---|---|---|
| **Two-tier evaluation** (deterministic → LLM judge) | Cheap checks cover most traces in <5ms at zero cost; the judge only does the semantic work the cheap layer gets wrong | The deterministic label can be briefly "stale" until the judge reconciles |
| **Async deep eval via Redis queue** | LLM calls are slow and rate-limited; keeping them off the ingest path keeps `POST /v1/traces` fast and resilient | Eventual consistency — a trace is diagnosed twice (quick, then deep) |
| **`LLMJudge` interface behind config** | Provider is a one-line swap (OpenAI ↔ Gemini's OpenAI-compatible endpoint); makes the judge unit-testable with a stub | A thin abstraction layer over the provider SDK |
| **Traces stored as JSONB** | The trace schema evolves fast; JSONB avoids migrations per field while still being queryable | Less rigid than fully normalized columns |
| **Fail-open everywhere** | No judge key, a 429 from the provider, or an unreachable Redis must never break ingest or the public demo | A degraded path silently falls back to the deterministic result |
| **Per-IP rate limit on the public demo** | The `/playground` endpoint is unauthenticated and burns shared LLM quota; a fixed-window Redis counter caps abuse | Fixed-window is coarser than a sliding window (acceptable for a demo) |

See [`docs/traceroai-system-plan.md`](docs/traceroai-system-plan.md) for the full design.

## Screenshots

| Trace detail — *the diagnosis* | Reliability dashboard |
|---|---|
| [![Trace detail](docs/media/trace-detail.png)](docs/media/trace-detail.png) | [![Dashboard](docs/media/dashboard.png)](docs/media/dashboard.png) |
| A wrong answer is a *symptom* — the trace shows the per-stage evaluation that explains the cause. | Trace volume, healthy rate, p95 latency, failure mix, and live deep-eval queue depth. |

## Quickstart

Install the SDK:

```bash
pip install traceroai
```

Instrument your RAG pipeline (context-manager style — auto-times the block and sends
the trace on exit):

```python
from traceroai import TraceroClient

client = TraceroClient(
    base_url="https://traceroai.onrender.com",
    api_key="your_project_key",
)

with client.trace("How long does a refund take?") as t:
    chunks = retrieve(query)              # your retriever
    t.log_retrieval(chunks, strategy="hybrid")
    answer = generate(prompt, chunks)     # your LLM
    t.log_generation(answer, model="gpt-4o-mini")
```

Then open the [dashboard](https://www.traceroai.tech) to inspect the trace — or
[try the live playground](https://www.traceroai.tech/docs) with no signup.

A complete, runnable example is in [`examples/simple-rag-monitored/`](examples/simple-rag-monitored/).

## Tech stack

| Layer | Stack |
|---|---|
| **API** | FastAPI · Pydantic · SQLAlchemy |
| **Storage** | Postgres (JSONB) · Redis (async deep-eval queue) |
| **Evaluation** | Deterministic evaluators · LLM-as-judge (OpenAI / Gemini, swappable) |
| **SDK** | Python (`httpx`), context-manager + decorator + low-level APIs |
| **Web** | Next.js · Tailwind CSS |
| **Deploy** | Render (API + colocated worker) · Vercel (web) · Neon (Postgres) · Upstash (Redis) |

## Repository structure

```
TraceroAI/
├── services/api/          FastAPI backend — ingest, evaluators, LLM judge, worker
│   └── app/
│       ├── api/routes/     traces · playground · eval_runs · jobs · health
│       ├── evaluators/     quick (deterministic) + deep (LLM judge) + diagnosis
│       └── services/       repositories · queue · rate limiter · judge
├── sdks/python/           the `traceroai` package published to PyPI
├── traceroai-web/         Next.js dashboard + interactive docs
├── examples/              a runnable, monitored RAG app
├── infra/                 docker-compose for local Postgres/Redis
└── docs/                  system design plan + media
```

## Running locally

```bash
# 1. Start Postgres + Redis
docker compose -f infra/docker-compose.yml up -d

# 2. API (+ tests)
cd services/api
python -m venv .venv && .venv/Scripts/activate     # or source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload

# 3. Web
cd ../../traceroai-web
npm install && npm run dev
```

Copy [`.env.example`](.env.example) to `.env` and fill in the connection strings and
(optionally) a judge API key.

## License

[MIT](./LICENSE)
