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
    base_url="https://traceroai.onrender.com",
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
client = TraceroClient(base_url="https://traceroai.onrender.com", api_key="your_project_key")
```

## Self-healing recovery (optional)

```bash
pip install "traceroai[recovery]"
```

`RecoveryAgent` (built on LangGraph) retries the RAG stage that TraceroAI diagnoses as
broken — re-retrieving on a retrieval miss, re-generating with a stricter prompt on an
unsupported claim — until the answer is healthy or it escalates to review. You supply
your own `retrieve`/`generate`; every attempt is traced.

```python
from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(client, retrieve=my_retrieve, generate=my_generate, max_attempts=3)
result = agent.run("How long does a refund take?")
# result["answer"], result["diagnosis"], result["attempts"], result["trace_ids"]
```

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

## Telemetry is best-effort

If the API is unreachable, the SDK warns and continues — it never breaks your app
or masks your own exceptions. Evaluations, diagnosis, and cost are computed
server-side (the server is the source of truth).
