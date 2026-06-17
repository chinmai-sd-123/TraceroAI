# Self-healing RAG — TraceroAI RecoveryAgent

A RAG pipeline that **fixes its own bad answers**, built on
[`traceroai[recovery]`](https://pypi.org/project/traceroai/) (LangGraph under the hood).

You supply a `retrieve(query, top_k)` and a `generate(query, context)`; the agent
runs them, evaluates each attempt via TraceroAI's server-side eval, and **retries the
stage that failed**:

| Diagnosis | Recovery action |
|---|---|
| `retrieval_miss` | raise `top_k`, rewrite the query → re-retrieve |
| `unsupported_claim` | inject a stricter grounding instruction → re-generate |
| `healthy_answer` / `correct_refusal` | stop — success |
| max attempts reached | stop — flag `needs_review` for a human |

The loop is driven by **fast quick eval** (embedding similarity); the **LLM judge**
confirms the final answer once (hybrid: cheap routing, rigorous final verdict). Every
attempt is sent as a trace, so the dashboard shows the full retry chain.

## Run

```bash
pip install -r requirements.txt        # traceroai[recovery] = + langgraph, langchain-openai
export OPENAI_API_KEY=sk-...
export TRACEROAI_API_URL=https://traceroai.onrender.com
export TRACEROAI_API_KEY=your_project_key    # optional
python app.py
```

Then open the dashboard, filter by the `recovery-agent` project, and watch a question
that started as a `retrieval_miss` recover to `healthy_answer` across attempts.

## The API

```python
from traceroai import TraceroClient
from traceroai.recovery import RecoveryAgent

agent = RecoveryAgent(
    client,
    retrieve=my_retrieve,   # (query, top_k) -> list[chunk dict]
    generate=my_generate,   # (query, context) -> answer str
    max_attempts=3,
)
result = agent.run("How long does a refund take?")
# result.answer, result.diagnosis, result.attempts, result.succeeded,
# result.trace_ids (the retry chain), result.deep_eval (final LLM-judge verdict)
```

## How it works

It's a LangGraph **state machine**: `retrieve → generate → evaluate`, with a
**conditional edge** that reads the diagnosis and routes recovery (loop back to
`retrieve` for retrieval problems, to `generate` for grounding problems), bounded by
`max_attempts` so it can never loop forever.
