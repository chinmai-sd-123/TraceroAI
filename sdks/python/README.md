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

client = TraceroClient(base_url="http://localhost:8000")

with client.trace("How long does a refund take?") as t:
    t.log_retrieval(chunks, strategy="hybrid", config={"final_top_k": 3})
    t.log_prompt(prompt_text, version="grounded_v1")
    t.log_generation(answer, model="gpt-4o-mini")

print(t.trace_id)
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
client = TraceroClient(base_url="https://api.traceroai.example", api_key="key_acme")
```
