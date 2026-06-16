"""A simple RAG app, monitored with TraceroAI.

What it shows: instrumenting a real (tiny) RAG pipeline so every answer becomes a
debuggable trace in the TraceroAI dashboard — using just `pip install traceroai`
and a few lines around your existing retrieve/generate code.

Run:
    pip install -r requirements.txt
    # optional, for real LLM answers (else an extractive fallback is used):
    export OPENAI_API_KEY=sk-...
    python app.py

Then open your dashboard (e.g. https://www.traceroai.tech/dashboard) to see the traces.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from traceroai import TraceroClient

from knowledge_base import DOCUMENTS


def _load_root_env() -> None:
    """TEMPORARY: read the repo-root .env so this example reuses the platform's
    config. Remove later — a real consumer app would set its own env vars."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_root_env()

# 1) Point the SDK at your deployed TraceroAI API.
TRACEROAI_API_URL = os.getenv("TRACEROAI_API_URL", "https://traceroai.onrender.com")
TRACEROAI_API_KEY = os.getenv("TRACEROAI_API_KEY")  # scopes traces to a project
client = TraceroClient(base_url=TRACEROAI_API_URL, api_key=TRACEROAI_API_KEY)


# 2) Build the retriever once: embed every document at startup.
_model = SentenceTransformer("all-MiniLM-L6-v2")
_doc_embeddings = _model.encode([doc["text"] for doc in DOCUMENTS], normalize_embeddings=True)


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Vector retrieval: cosine similarity between the query and each document."""
    q = _model.encode([query], normalize_embeddings=True)[0]
    scores = _doc_embeddings @ q  # cosine, since everything is normalized
    ranked = sorted(zip(DOCUMENTS, scores), key=lambda pair: pair[1], reverse=True)
    return [
        {
            "rank": i + 1,
            "chunk_id": doc["id"],
            "document_title": doc["title"],
            "source": doc["source"],
            "final_score": round(float(score), 4),
            "text": doc["text"],
        }
        for i, (doc, score) in enumerate(ranked[:top_k])
    ]


def build_prompt(query: str, chunks: list[dict]) -> str:
    context = "\n\n".join(f"[{c['rank']}] {c['text']}" for c in chunks)
    return (
        "Answer the question using ONLY the context below. Cite sources like [1]. "
        "If the context does not contain the answer, say you don't know.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    )


# Generation reuses the platform's provider config from the root .env (TEMP):
# TRACEROAI_OPENAI_API_KEY / _JUDGE_MODEL / _JUDGE_BASE_URL. Falls back to the
# GEN_* vars if you ever run this as a standalone app.
GEN_API_KEY = os.getenv("GEN_API_KEY") or os.getenv("TRACEROAI_OPENAI_API_KEY")
GEN_BASE_URL = (os.getenv("GEN_BASE_URL") or os.getenv("TRACEROAI_JUDGE_BASE_URL") or "").strip() or None
GEN_MODEL = os.getenv("GEN_MODEL") or os.getenv("TRACEROAI_JUDGE_MODEL", "gpt-4o-mini")
GEN_PROVIDER = "google" if (GEN_BASE_URL and "googleapis" in GEN_BASE_URL) else "openai"


def _extractive(chunks: list[dict]) -> str:
    return chunks[0]["text"] if chunks else "I don't know based on the provided context."


def generate(prompt: str, chunks: list[dict]) -> str:
    """Generate via the configured LLM; fall back to extractive if no key or the
    provider errors (e.g. quota/429) — so the demo always produces a trace."""
    if not GEN_API_KEY:
        return _extractive(chunks)
    try:
        from openai import OpenAI

        client = OpenAI(api_key=GEN_API_KEY, base_url=GEN_BASE_URL)
        completion = client.chat.completions.create(
            model=GEN_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content or _extractive(chunks)
    except Exception as exc:
        print(f"   (LLM unavailable: {exc.__class__.__name__}; using extractive fallback)")
        return _extractive(chunks)


def answer_question(query: str) -> str:
    """The RAG call — fully instrumented with TraceroAI."""
    with client.trace(query) as t:
        chunks = retrieve(query)
        t.log_retrieval(chunks, strategy="vector", config={"final_top_k": 3})

        prompt = build_prompt(query, chunks)
        t.log_prompt(prompt, version="simple_v1", template_name="grounded_answer")

        answer = generate(prompt, chunks)
        t.log_generation(answer, model=GEN_MODEL, provider=GEN_PROVIDER)

        print(f"\nQ: {query}\nA: {answer}\n   → trace: {t.trace_id}")
        return answer


if __name__ == "__main__":
    questions = [
        "How long does a refund take?",
        "What plans do you offer?",
        "How do I reset my password?",
        "Do you offer a free trial?",  # not in the KB → should retrieve-miss
    ]
    print(f"Sending traces to {TRACEROAI_API_URL} ...")
    for q in questions:
        answer_question(q)
        time.sleep(0.3)
    print("Done. Open your TraceroAI dashboard to inspect the traces.")
