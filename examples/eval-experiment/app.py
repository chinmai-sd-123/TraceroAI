"""RAG experiment evaluation, run through the TraceroAI SDK.

This is a *client* of TraceroAI: it brings its own RAG pipeline (retrieve +
generate) and a labeled dataset, then uses `traceroai.eval.run_experiment` to
compare pipeline configs, grade answers with TraceroAI's server-side judge, and
post the result to the dashboard. Nothing about the pipeline lives in the
platform — exactly how a real user would integrate.

Run:
    pip install -r requirements.txt
    export OPENAI_API_KEY=sk-...        # for this app's own retriever + generator
    export TRACEROAI_API_URL=https://traceroai.onrender.com
    export TRACEROAI_API_KEY=your_project_key
    python app.py
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from traceroai import TraceroClient
from traceroai.eval import Case, Variant, run_experiment

load_dotenv(Path(__file__).parent / ".env")

from dataset import CASES  # noqa: E402  (after load_dotenv)

# Reuse the recovery-agent example's docs as the knowledge base.
_DOCS_DIR = Path(__file__).resolve().parents[1] / "recovery-agent" / "docs"

_store = None
_llm = None


def _ensure_clients() -> None:
    global _store, _llm
    if _store is None:
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
        docs: list[Document] = []
        for path in sorted(_DOCS_DIR.glob("*")):
            if path.suffix.lower() in {".md", ".txt"}:
                for chunk in splitter.split_text(path.read_text(encoding="utf-8")):
                    docs.append(Document(page_content=chunk, metadata={"title": path.stem}))
        _store = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings(model="text-embedding-3-small"))
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def retrieve(query: str, top_k: int) -> list[dict]:
    _ensure_clients()
    docs = _store.similarity_search(query, k=top_k)
    return [{"rank": i + 1, "chunk_id": f"c{i}", "text": d.page_content}
            for i, d in enumerate(docs)]


def generate(query: str, context: str) -> str:
    _ensure_clients()
    prompt = (
        "Answer using ONLY the context. If it lacks the answer, say you don't know "
        "based on the provided context.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    )
    return _llm.invoke(prompt).content


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY (or fill .env) to run this example.")

    client = TraceroClient(
        base_url=os.getenv("TRACEROAI_API_URL", "https://traceroai.onrender.com"),
        api_key=os.getenv("TRACEROAI_API_KEY"),
    )

    result = run_experiment(
        client=client,
        dataset=[Case(c["id"], c["question"], c["expected"]) for c in CASES],
        retrieve=retrieve,
        generate=generate,
        variants=[
            Variant("k2", "top_k=2", top_k=2),
            Variant("k3", "top_k=3", top_k=3),
            Variant("k5", "top_k=5", top_k=5),
        ],
        project_id="eval-experiment",
        dataset_name="Support FAQ",
    )

    print(f"\n>>> {result.recommendation}")
    for v in result.variants:
        acc = next((m["score"] for m in v["metrics"] if m["metric_name"] == "accuracy"), None)
        print(f"  {v['name']:10} accuracy={acc}  avg_latency={v['average_latency_ms']}ms")
    print(f"\neval_run_id: {result.eval_run_id}")
    print("Open the dashboard (project 'eval-experiment') to see the run.")
