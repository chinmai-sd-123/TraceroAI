"""Self-healing RAG with TraceroAI's RecoveryAgent (LangGraph).

You bring a retriever and a generator; the agent runs them, evaluates each attempt
via TraceroAI, and retries the stage that failed — re-retrieving with more context
on a retrieval miss, re-generating with a stricter prompt on an unsupported claim —
until the answer is healthy or it gives up and flags it for review. Every attempt is
traced, so the dashboard shows the full retry chain.

Run:
    pip install -r requirements.txt          # installs traceroai[recovery]
    export OPENAI_API_KEY=sk-...
    export TRACEROAI_API_URL=https://traceroai.onrender.com
    export TRACEROAI_API_KEY=your_project_key   # optional
    python app.py
"""

from __future__ import annotations

import os
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from traceroai import TraceroClient
from traceroai.recovery import RecoveryAgent

# Knowledge base = real files (.md and .txt) under docs/. This is the realistic
# ingestion flow: load files -> split into chunks -> embed. Add more files (or
# more formats via other LangChain loaders) and they're picked up automatically.
_DOCS_DIR = Path(__file__).parent / "docs"


def _load_documents() -> list[Document]:
    """Load every .md/.txt file in docs/ and split into retrievable chunks.

    Because the documents are large, splitting matters: each file becomes several
    chunks, so top-k retrieval returns the most relevant passages (and a retrieval
    miss has real meaning — the agent can re-retrieve with a higher top_k)."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    docs: list[Document] = []
    for path in sorted(_DOCS_DIR.glob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        for i, chunk in enumerate(splitter.split_text(text)):
            docs.append(
                Document(page_content=chunk, metadata={"title": path.stem, "chunk": i})
            )
    if not docs:
        raise RuntimeError(f"No .md/.txt documents found in {_DOCS_DIR}")
    return docs


# Clients are built lazily (the first call) so importing this module needs no API
# key — the key is only required when you actually run the pipeline.
_store = None
_llm = None


def _ensure_clients() -> None:
    global _store, _llm
    if _store is None:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        _store = InMemoryVectorStore.from_documents(_load_documents(), embeddings)
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# --- the two functions YOU supply to the agent -------------------------------
def retrieve(query: str, top_k: int) -> list[dict]:
    """Vector retrieval -> TraceroAI chunk shape. top_k is controlled by the agent
    (it raises top_k when it diagnoses a retrieval miss)."""
    _ensure_clients()
    docs = _store.similarity_search(query, k=top_k)
    return [
        {"rank": i + 1, "chunk_id": f"kb_{i + 1}",
         "document_title": d.metadata.get("title", ""), "text": d.page_content}
        for i, d in enumerate(docs)
    ]


def generate(query: str, context: str) -> str:
    """Generate an answer from the retrieved context. The agent injects a stricter
    grounding instruction into `query` when it diagnoses an unsupported claim."""
    _ensure_clients()
    prompt = (
        f"Answer the question using ONLY the context. Cite like [1]. "
        f"If the context lacks the answer, say you don't know.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    )
    return _llm.invoke(prompt).content


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY to run this example.")

    client = TraceroClient(
        base_url=os.getenv("TRACEROAI_API_URL", "https://traceroai.onrender.com"),
        api_key=os.getenv("TRACEROAI_API_KEY"),
    )
    agent = RecoveryAgent(
        client,
        retrieve=retrieve,
        generate=generate,
        max_attempts=3,
        project_id="recovery-agent",
    )

    questions = [
        "How long does a refund take?",          # answerable -> should go healthy
        "Can I change my workspace region later?",  # answerable
        "What is your phone support number?",     # NOT in KB -> should end needs_review
    ]
    for q in questions:
        result = agent.run(q)
        status = "✓ healthy" if result["succeeded"] else "⚠ needs review"
        print(f"\nQ: {q}")
        print(f"  {status} after {result['attempts']} attempt(s) — {result['diagnosis']}")
        print(f"  answer: {result['answer'][:100]}")
        print(f"  retry chain (trace ids): {result['trace_ids']}")
        if result["deep_eval"]:
            print(f"  deep verdict: {[e.get('label') for e in result['deep_eval']]}")

    print("\nOpen your TraceroAI dashboard (project 'recovery-agent') to see the retry chains.")
