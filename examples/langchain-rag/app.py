"""LangChain RAG pipeline monitored with TraceroAI — three integration styles.

Shows every TraceroAI SDK surface against a real LangChain LCEL pipeline:

  1. Explicit context manager  -> client.trace() + log_retrieval/log_prompt/log_generation
  2. Decorator                 -> @client.traced(...)
  3. Callback handler          -> zero-touch auto-instrumentation

Run:
    pip install -r requirements.txt
    export OPENAI_API_KEY=sk-...
    export TRACEROAI_API_URL=https://traceroai.onrender.com   # or your local API
    export TRACEROAI_API_KEY=your_project_key                 # optional
    python app.py
"""

from __future__ import annotations

import os

from traceroai import TraceroClient

from rag_chain import (
    PROMPT,
    build_chain,
    build_llm,
    build_retriever,
    docs_to_chunks,
    format_context,
)
from tracero_callback import TraceroAICallbackHandler

client = TraceroClient(
    base_url=os.getenv("TRACEROAI_API_URL", "https://traceroai.onrender.com"),
    api_key=os.getenv("TRACEROAI_API_KEY"),
)


# ---------------------------------------------------------------------------
# Style 1: Explicit context manager — log each pipeline stage by hand.
# Best when you want full control / to log the prompt and retrieval config.
# ---------------------------------------------------------------------------
def ask_with_context_manager(question: str) -> str:
    retriever = build_retriever()
    llm = build_llm()

    with client.trace(question, project={"project_id": "langchain-demo"},
                       metadata={"integration": "context_manager"}) as t:
        docs = retriever.invoke(question)
        t.log_retrieval(docs_to_chunks(docs), strategy="vector",
                        config={"top_k": len(docs)})

        context = format_context(docs)
        messages = PROMPT.format_messages(context=context, question=question)
        t.log_prompt(messages[-1].content, version="grounded_v1",
                     template_name="rag_qa")

        answer = llm.invoke(messages).content
        t.log_generation(answer, model=llm.model_name, provider="openai")

    print(f"[context-manager] {question}\n  -> {answer}\n  trace: {t.trace_id}\n")
    return answer


# ---------------------------------------------------------------------------
# Style 2: Decorator — wrap a function that returns (answer, chunks).
# Best for the common case: one call, minimal ceremony.
# ---------------------------------------------------------------------------
@client.traced(model="gpt-4o-mini", strategy="vector")
def ask_with_decorator(question: str):
    retriever = build_retriever()
    llm = build_llm()
    docs = retriever.invoke(question)
    answer = llm.invoke(PROMPT.format_messages(context=format_context(docs),
                                               question=question)).content
    return answer, docs_to_chunks(docs)


# ---------------------------------------------------------------------------
# Style 3: Callback handler — attach to the composed LCEL chain; zero manual logging.
# Best for idiomatic LangChain apps already using callbacks.
# ---------------------------------------------------------------------------
def ask_with_callback(question: str) -> str:
    chain = build_chain()
    handler = TraceroAICallbackHandler(client, project_id="langchain-demo")
    answer = chain.invoke(question, config={"callbacks": [handler]})
    print(f"[callback] {question}\n  -> {answer}\n  trace: {handler.trace_id}\n")
    return answer


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY to run this example.")

    print("=== Style 1: explicit context manager ===")
    ask_with_context_manager("How long does a refund take?")

    print("=== Style 2: decorator ===")
    answer = ask_with_decorator("What plans do you offer?")
    print(f"[decorator] -> {answer}\n")

    print("=== Style 3: callback handler ===")
    ask_with_callback("Can I change my workspace region after creating it?")

    print("Done. Open your TraceroAI dashboard to inspect the traces.")
