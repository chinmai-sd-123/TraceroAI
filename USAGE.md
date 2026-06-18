# TraceroAI — Usage Guide

How to instrument any RAG pipeline with the `traceroai` SDK, what each feature does,
and how to read the results in the dashboard.

- **Install:** `pip install traceroai`
- **API base URL:** `https://traceroai.onrender.com` (or your own deployment)
- **Dashboard:** https://www.traceroai.tech/dashboard
- **PyPI:** https://pypi.org/project/traceroai/

---

## 1. The client

Everything starts with a `TraceroClient`. It only needs your API base URL; an API key
is optional and scopes traces to a project.

```python
from traceroai import TraceroClient

client = TraceroClient(
    base_url="https://traceroai.onrender.com",
    api_key="your_project_key",   # optional — omit for the open demo
    timeout_seconds=10.0,          # optional
)
```

**What the API key does:** if the server has your key mapped to a project, every trace
you send is stamped with that project, and the dashboard can filter to it. Without a
key, traces use whatever `project_id` you pass (or none).

---

## 2. Sending traces — three styles

The SDK gives you three ways to instrument a RAG call, from most explicit to most
automatic. They all produce the same kind of trace.

### a) Context manager (recommended)

Times the block automatically and sends the trace on exit. Log each stage as it happens.

```python
with client.trace("How long does a refund take?") as t:
    chunks = retrieve(query)                       # your retriever
    t.log_retrieval(chunks, strategy="hybrid", config={"top_k": 3})

    prompt = build_prompt(query, chunks)
    t.log_prompt(prompt, version="grounded_v1")    # optional

    answer = generate(prompt)                      # your LLM
    t.log_generation(answer, model="gpt-4o-mini", provider="openai")

print(t.trace_id)   # the id of the sent trace (None if sending failed)
```

- **`log_retrieval(chunks, strategy=..., config=...)`** — `chunks` is a list of dicts;
  each chunk should have at least a `text` field (and optionally `rank`, `chunk_id`,
  `document_title`, `final_score`).
- **`log_prompt(content, version=..., template_name=...)`** — optional; record the
  prompt that was sent so you can correlate prompt versions with quality.
- **`log_generation(answer, model=..., provider=..., temperature=...)`** — the model's
  answer. `model` is required.

**Best-effort by design:** if the trace fails to send (network down, API unreachable),
the SDK warns and continues — it never breaks your app or masks your own exceptions.
If an exception escapes the `with` block, the trace is still sent, marked unanswered.

### b) Decorator

For a function that returns `(answer, chunks)`. The first positional arg is treated as
the query.

```python
@client.traced(model="gpt-4o-mini", strategy="vector")
def answer(query: str):
    chunks = retrieve(query)
    return generate(query, chunks), chunks   # (answer, chunks)

answer("What plans do you offer?")   # traced automatically
```

### c) Low-level

Full control — assemble and send a trace in one call. Use when you already have all the
pieces.

```python
trace_id = client.log_trace(
    query={"original": question},
    retrieval={"strategy": "hybrid", "chunks": chunks},
    generation={"model": "gpt-4o-mini", "answer": answer},
    prompt={"content": prompt},          # optional
    latency={"total_ms": 1171},          # optional
    project={"project_id": "my-app"},    # optional
    metadata={"env": "prod"},            # optional
)
```

> **Note:** `evaluations` and `diagnosis` are computed **server-side** (the server is the
> source of truth), so you don't send them — anything you send would be ignored.

---

## 3. Reading a trace back

```python
trace = client.get_trace(trace_id)
print(trace["diagnosis"]["label"])          # e.g. "healthy_answer"
print(trace["evaluations"]["quick"])         # embedding/lexical relevance + groundedness
print(trace["evaluations"]["deep"])          # LLM-judge results (async; may be empty at first)
```

---

## 4. What the server evaluates (so you can read the dashboard)

Every trace is scored on two tiers and reduced to **one diagnosis**:

**Quick (synchronous, on every trace):**
- `context_relevance` — embedding cosine similarity between query and retrieved context
- `answer_relevance` — embedding cosine similarity between query and answer
- `groundedness` — term overlap between answer and context

**Deep (asynchronous, LLM-as-judge):**
- claim-level groundedness, plus relevance verdicts with reasons

**Diagnosis — one of six labels:**

| Label | Meaning | Likely fix |
|---|---|---|
| `healthy_answer` | retrieval, grounding, relevance all pass | — |
| `correct_refusal` | model rightly declined (context lacked the answer) | — |
| `retrieval_miss` | retrieved context doesn't match the query | improve retrieval / raise top_k |
| `unsupported_claim` | answer asserts things the context doesn't support | stricter grounding prompt |
| `wrong_answer` | answer doesn't address the query | check prompt / retrieval |
| `needs_review` | mixed signals | inspect manually |

---

## 5. Self-healing recovery (optional extra)

```bash
pip install "traceroai[recovery]"
```

`RecoveryAgent` wraps your RAG in a LangGraph loop that **fixes its own bad answers**.
You supply `retrieve` and `generate`; the agent evaluates each attempt via TraceroAI and
retries the stage that failed.

```python
from traceroai import TraceroClient
from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(
    client,
    retrieve=my_retrieve,    # (query, top_k) -> list[chunk dict]
    generate=my_generate,    # (query, context) -> answer str
    max_attempts=3,
    project_id="recovery-agent",
)

result = agent.run("How long does a refund take?")
result["answer"]       # final answer
result["diagnosis"]    # final diagnosis label
result["attempts"]     # how many tries it took
result["succeeded"]    # True if it reached a healthy answer
result["trace_ids"]    # the retry chain (one trace per attempt)
result["deep_eval"]    # final LLM-judge verdict (or None if still pending)
```

**How recovery routes:**

| Diagnosis | Recovery action |
|---|---|
| `retrieval_miss` | raise `top_k`, rewrite the query → re-retrieve |
| `unsupported_claim` | inject a stricter grounding instruction → re-generate |
| `healthy_answer` / `correct_refusal` | stop — success |
| max attempts reached | stop — flag `needs_review` |

The loop is bounded by `max_attempts` (plus a hard recursion limit), so it can never
loop forever. See [`examples/recovery-agent/`](examples/recovery-agent/) for a runnable
demo that loads `.md`/`.txt` documents, splits them, and recovers across attempts.

---

## 6. Experiment runs (A/B-test pipeline configs)

Compare pipeline configurations against a labeled dataset and get a recommended
winner — using `traceroai.eval`. You bring your own `retrieve`/`generate` and cases;
each answer is graded by the server-side judge (single source of truth), the best
variant is recommended, and the run is posted to the eval-runs API.

```python
from traceroai import TraceroClient
from traceroai.eval import run_experiment, Case, Variant

run_experiment(
    client=TraceroClient(base_url="https://traceroai.onrender.com", api_key="your_project_key"),
    dataset=[Case("c1", "How long does a refund take?", "5-7 business days.")],
    retrieve=my_retrieve,   # (query, top_k) -> list[chunk dict]
    generate=my_generate,   # (query, context) -> answer str
    variants=[Variant("k3", "top_k=3", top_k=3), Variant("k5", "top_k=5", top_k=5)],
    project_id="my-app",
)
```

The run appears under **Eval Runs** in the dashboard, filterable by project. Each
variant reports **accuracy** (correct vs. expected answers, judged server-side) and
**average latency**; the highest-accuracy variant is recommended. A complete runnable
example is in [`examples/eval-experiment/`](examples/eval-experiment/).

---

## 7. Loading your own documents (any format)

TraceroAI does **not** load documents — that's your retriever's job, which is why the
SDK works with any source (text files, markdown, PDFs, a vector DB, an API). Use a
loader (e.g. LangChain's) to produce chunks, then return them from `retrieve`:

```python
from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# load .txt / .md / .pdf ... -> split -> embed into a vector store -> retrieve
```

`examples/recovery-agent/` shows the full flow: load a `docs/` folder of `.md` + `.txt`
files, split with `RecursiveCharacterTextSplitter`, embed, and retrieve top-k.

---

## 8. Examples in this repo

| Example | Shows |
|---|---|
| [`examples/langchain-rag/`](examples/langchain-rag/) | A LangChain LCEL pipeline traced three ways (context manager, decorator, callback handler) |
| [`examples/recovery-agent/`](examples/recovery-agent/) | Self-healing recovery with real `.md`/`.txt` document ingestion |
| [`examples/simple-rag-monitored/`](examples/simple-rag-monitored/) | A minimal monitored RAG app |
