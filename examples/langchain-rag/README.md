# LangChain RAG + TraceroAI

A real [LangChain](https://python.langchain.com) LCEL RAG pipeline (OpenAI
retriever → prompt → chat model), instrumented with [TraceroAI](https://pypi.org/project/traceroai/)
**three different ways** — so every SDK surface is demonstrated against a real chain.

## What it shows

| Style | File | SDK surface | When to use |
|---|---|---|---|
| **Context manager** | `app.py` → `ask_with_context_manager` | `client.trace()`, `log_retrieval`, `log_prompt`, `log_generation` | Full control; log the prompt + retrieval config per stage |
| **Decorator** | `app.py` → `ask_with_decorator` | `@client.traced(...)` | One call, minimal ceremony — function returns `(answer, chunks)` |
| **Callback handler** | `tracero_callback.py` | low-level `log_trace` via LangChain `BaseCallbackHandler` | Idiomatic, zero-touch auto-instrumentation for existing chains |

All three send a trace that appears in the TraceroAI dashboard with retrieval,
prompt, answer, latency, and a server-computed diagnosis.

## Run

```bash
pip install -r requirements.txt

export OPENAI_API_KEY=sk-...
export TRACEROAI_API_URL=https://traceroai.onrender.com   # or http://127.0.0.1:8000
export TRACEROAI_API_KEY=your_project_key                 # optional — scopes traces to a project

python app.py
```

Then open your dashboard (e.g. https://www.traceroai.tech/dashboard) — filter by
the `langchain-demo` project to see the traces.

## How it maps

```
LangChain step            ->  TraceroAI field
-------------------------     ----------------------------
retriever.invoke(q)       ->  log_retrieval(chunks, strategy, config)
PROMPT.format_messages    ->  log_prompt(content, version, template_name)
llm.invoke(messages)      ->  log_generation(answer, model, provider)
(wall-clock of the block) ->  latency.total_ms   (auto, context manager)
```

The pipeline itself lives in `rag_chain.py`; `docs_to_chunks` adapts LangChain
`Document`s into TraceroAI's retrieval-chunk shape.

## Notes

- **Best-effort telemetry:** if the TraceroAI API is unreachable, the SDK (and the
  callback handler) warn and continue — your chain never breaks.
- **Models:** defaults to `gpt-4o-mini` + `text-embedding-3-small`; override via
  `OPENAI_CHAT_MODEL` / `OPENAI_EMBED_MODEL` / `RAG_TOP_K`.
