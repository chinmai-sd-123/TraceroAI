# Simple RAG, monitored with TraceroAI

A minimal, standalone RAG app that shows how to **monitor any RAG pipeline** with
[TraceroAI](https://github.com/chinmai-sd-123/TraceroAI) using just the published
SDK (`pip install traceroai`). It is **not** part of the platform — it's an example
of a *consumer* app that sends traces to a running TraceroAI API.

## What it does
- Embeds a tiny knowledge base (`sentence-transformers`, local, free)
- Retrieves by cosine similarity, builds a grounded prompt, generates an answer
- Wraps the whole call in `client.trace(...)` so **every answer becomes a trace**
  in the dashboard — with retrieved chunks, scores, prompt, answer, evaluators,
  and a diagnosis (healthy / retrieval miss / unsupported claim / ...)

## Run it
```bash
pip install -r requirements.txt

# optional — real LLM answers (otherwise an extractive fallback is used):
export OPENAI_API_KEY=sk-...

# point at your TraceroAI API (defaults to the deployed one):
export TRACEROAI_API_URL=https://traceroai.onrender.com

python app.py
```

Then open the dashboard (e.g. `https://www.traceroai.tech/dashboard`) — your four
demo questions appear as traces, including a deliberate "free trial" question that
isn't in the knowledge base (watch it get diagnosed as a retrieval miss).

## The only TraceroAI-specific code

```python
from traceroai import TraceroClient
client = TraceroClient(base_url="https://traceroai.onrender.com")

with client.trace(query) as t:
    chunks = retrieve(query)
    t.log_retrieval(chunks, strategy="vector")
    answer = generate(build_prompt(query, chunks), chunks)
    t.log_generation(answer, model="gpt-4o-mini")
```

That's the entire integration. Everything else is ordinary RAG code you'd write anyway.
