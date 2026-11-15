# TraceroAI Python SDK

Send RAG traces to [TraceroAI](https://github.com/chinmai-sd-123/TraceroAI) — a
RAG observability and evaluation platform. Instrument any RAG pipeline
(LangChain, LlamaIndex, or your own) and every answer becomes a debuggable trace.

## Install

```bash
pip install traceroai
```

## Usage

### Context manager (recommended)

Times the block and sends the trace automatically:

```python
from traceroai import TraceroClient

client = TraceroClient(
    base_url="http://localhost:8000",
    api_key="your_project_key",
)

with client.trace("How long does a refund take?") as t:
    t.log_retrieval(chunks, strategy="hybrid", config={"final_top_k": 3})
    t.log_prompt(prompt_text, version="grounded_v1")
    t.log_generation(
        answer,
        model="gpt-4o-mini",
        temperature=0,
        parameters={"top_p": 1, "max_tokens": 512},   # any tunable knobs
        prompt_tokens=1200, completion_tokens=80,      # -> server computes cost
    )

print(t.trace_id)
```

Read a trace back (server-computed diagnosis + evaluations):

```python
trace = client.get_trace(t.trace_id)
trace["diagnosis"]["label"]      # e.g. "healthy_answer"
trace["generation"]["usage"]     # tokens + cost_usd
```

### Decorator

For a function that returns `(answer, chunks)`:

```python
@client.traced(model="gpt-4o-mini", strategy="hybrid")
def answer(query: str):
    chunks = retrieve(query)
    return generate(query, chunks), chunks

answer("What is the maximum file upload size?")  # traced automatically
```

### Low-level

```python
client.log_trace(
    query={"original": question},
    retrieval={"strategy": "hybrid", "chunks": chunks},
    generation={"model": "gpt-4o-mini", "answer": answer},
)
```

## Authentication (multi-tenant)

Pass your project API key; the server attributes traces to your project:

```python
client = TraceroClient(base_url="http://localhost:8000", api_key="your_project_key")
```

## Self-healing recovery (optional)

```bash
pip install "traceroai[recovery]"
```

`RecoveryAgent` (built on LangGraph) retries the RAG stage that TraceroAI diagnoses as
broken — re-retrieving on a retrieval miss, re-generating with a stricter prompt on an
unsupported claim or a wrong answer — until the answer is healthy or it escalates to
review. You supply your own `retrieve`/`generate`; every attempt is traced.

```python
from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(client, retrieve=my_retrieve, generate=my_generate, max_attempts=3)
result = agent.run("How long does a refund take?")
# result["answer"], result["diagnosis"], result["attempts"], result["trace_ids"]
```

Every attempt is a trace, and all attempts of one `run()` share a
`metadata.recovery_run_id`, so the dashboard shows each run as one chain. On a retrieval
miss the agent retrieves more chunks (`top_k` + 2); pass `rewrite=` (a
`question -> query` function, such as an LLM call) to also rephrase the query. Each
attempt records the `top_k` and query it used. If your `retrieve` or `generate` raises,
that attempt is traced with status `error` and the exception is raised from `run()`.

`generate` may return just the answer, or `(answer, {"prompt_tokens": ..., "completion_tokens": ...})` —
return the token counts and each recovery attempt's trace gets a server-computed cost.

**Routing is judge-driven.** Each attempt is evaluated by the server's LLM judge
synchronously, and the agent retries only when that judge says the answer failed.
`result["diagnosis_source"]` says where the final verdict came from: `"judge"`, or
`"embedding"` / `"lexical"` when the server has no judge and the diagnosis is a quick-check
estimate. On such an estimate the agent stops after the first attempt and reports it,
because the quick checks often flag correct answers and every retry costs a generation.
Pass `retry_on_quick_diagnosis=True` to retry on estimates anyway.

## Experiment evaluation

A/B-test pipeline configs against a labeled dataset. Bring your own
`retrieve`/`generate` and cases; each answer is graded by TraceroAI's server-side
judge, the best variant is recommended, and the run shows up on your dashboard.

```python
from traceroai.eval import run_experiment, Case, Variant

run_experiment(
    client=client,
    dataset=[Case("c1", "How long does a refund take?", "5-7 business days.")],
    retrieve=my_retrieve,   # (query, top_k) -> list[chunk dict]
    generate=my_generate,   # (query, context) -> answer str
    variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
    project_id="my-app",
)
```

## Sending is non-blocking and best-effort

Traces go onto an in-memory queue and a background thread sends them, so tracing
adds well under a millisecond to your request path and a slow or unreachable
TraceroAI server never holds your code up. The SDK never raises into your code
when a send fails: failures are retried (timeouts, 429, 5xx, with backoff), then
logged on the `traceroai` logger.

- **Short-lived processes** (scripts, serverless handlers, tests): call
  `client.flush()` before exiting. An exit hook also flushes for up to 2 seconds.
- **Trace ids** are generated by the client: `t.trace_id` is set as soon as the
  `with` block starts, and a retried send reuses it, so the server never stores a
  trace twice.
- **Reading back**: `client.get_trace()` waits for queued sends first.
- **Full queue** (1,000 traces by default): new traces are dropped and counted in
  `client.dropped_traces` rather than using more memory.
- **Async code**: `@client.traced` works on `async def` functions.

Configuration:

```python
TraceroClient(
    base_url=None,          # default: TRACEROAI_API_URL
    api_key=None,           # default: TRACEROAI_API_KEY
    enabled=None,           # default: TRACEROAI_ENABLED (false/0/off disables sending)
    background=True,        # False: send in the calling thread (still never raises)
    raise_on_error=False,   # with background=False, raise TraceroError on failure
    max_queue_size=1000,
    max_retries=3,
)
```

Evaluations, diagnosis, and cost are computed server-side.

### Chunks

`log_retrieval` (and `log_trace`) take dicts, strings, or LangChain `Document` objects.
Missing `rank`s and `chunk_id`s are filled in from position, and chunks with no text are
left out, so a trace is never rejected over a chunk's shape.

### Async code

For asyncio applications use `AsyncTraceroClient`. It sends traces as tasks on the
running event loop (no thread), with the same retries and the same promise never to
raise into your code. `log_trace` and the context manager return at once; the calls
that wait are coroutines.

```python
from traceroai import AsyncTraceroClient

client = AsyncTraceroClient(base_url="http://localhost:8000")

async def answer(question: str) -> str:
    async with client.trace(question) as t:     # plain `with` works too
        chunks = await retrieve(question)
        t.log_retrieval(chunks)
        reply = await generate(question, chunks)
        t.log_generation(reply, model="gpt-4o-mini")
    return reply

trace = await client.get_trace(trace_id)          # sends pending traces first
await client.aclose()                             # on shutdown: send what's pending
```

`@client.traced(model=...)` wraps `async def` functions. The sync `TraceroClient` also
works in async code, and has `aget_trace`, `alog_trace_sync_eval` and `aflush` for the
calls that wait.

### Changes in 0.5.0

- Sending moved to a background thread; `log_trace` returns immediately with a
  client-generated id instead of waiting for the server's response.
- `t.trace_id` is always set (it used to be `None` when sending failed).
- Send failures are logged on the `traceroai` logger instead of raised
  (`log_trace`) or emitted as `UserWarning` (context manager).
- `@client.traced` supports async functions and keeps the function's name.
- `RecoveryAgent` no longer appends "(be specific and complete)" to the query on a
  retrieval miss; pass `rewrite=` to rephrase it. Attempts carry a shared run id, and
  a failure in your `retrieve`/`generate` is traced before it's raised.
- `RecoveryAgent` retries only on LLM-judge verdicts unless
  `retry_on_quick_diagnosis=True`, and returns `diagnosis_source`.
- Chunks are normalised before sending (see Chunks above).
- `run_experiment` keeps its results when posting the run fails, and reports why
  cases couldn't be graded, in `result.errors`.
- The `[recovery]` extra installs only `langgraph`; install your own LLM client.
- New: `AsyncTraceroClient` for asyncio code (see Async code above).
- New: `flush()`, `close()`, `dropped_traces`, `TraceroError`, `__version__`,
  configuration from environment variables, `aget_trace`/`alog_trace_sync_eval`/`aflush`,
  and type information (`py.typed`).
- Supports Python 3.10 and later (was 3.11).
