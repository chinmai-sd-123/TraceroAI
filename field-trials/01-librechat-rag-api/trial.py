"""Field trial 1: LibreChat's rag_api, instrumented with TraceroAI.

rag_api (MIT, github.com/LibreChat-AI/rag-api) stores and searches chunks; the LLM
answer happens in LibreChat. This script plays LibreChat's part: it asks rag_api for
chunks, answers with gpt-4o-mini using a prompt modelled on LibreChat's file-context
prompt, and traces every run to a local TraceroAI stack.

Run from services/api (the provider key comes from TraceroAI's settings and is
never printed), with rag_api on :8100 and TraceroAI on :8000.

    python trial_ragapi.py ingest <tag>                     # embed the corpus as file ids <tag>-<page>
    python trial_ragapi.py run <tag> <k> <prompt> <set>      # trace every question in a set
    python trial_ragapi.py experiment <set> <variant> ...   # variant = id:tag:k:prompt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from openai import OpenAI

HERE = Path(__file__).parent
REPO = Path(__file__).resolve().parents[2]  # the TraceroAI checkout
sys.path.insert(0, str(REPO / "sdks" / "python"))
sys.path.insert(0, str(REPO / "services" / "api"))

from app.core.config import get_settings  # noqa: E402
from traceroai import TraceroClient  # noqa: E402
from traceroai.eval import Case, Variant, run_experiment  # noqa: E402

RAG = "http://localhost:8100"
TRACERO = "http://localhost:8000"
PROJECT = "trial-rag-api"
CORPUS = HERE / "corpus"  # fetched by fetch_corpus.sh
PAGES = sorted(CORPUS.glob("*.md"))
MODEL = "gpt-4o-mini"
# USD per million tokens, for the spending cap (gpt-4o-mini list price).
PRICE_IN, PRICE_OUT = 0.15, 0.60
BUDGET_USD = 0.50
SPEND_FILE = HERE / "results" / "spend.json"

PROMPTS = {
    # Modelled on the context LibreChat wraps around rag_api's chunks.
    "librechat": (
        "The user has attached files to the conversation. Here is the relevant context from them:\n\n"
        "<context>\n{context}\n</context>\n\n"
        "Use the context as your learned knowledge to better answer the user.\n"
        "In your response, remember to follow these guidelines:\n"
        "- If you don't know the answer, simply say that you don't know.\n"
        "- If you are unsure how to answer, ask for clarification.\n"
        "- Avoid mentioning that you obtained the information from the context."
    ),
    # The change TraceroAI's diagnoses point to when answers claim more than the context.
    "grounded": (
        "Answer the question using only the numbered context below. Be specific: keep the exact names,\n"
        "defaults, ordering and conditions the context gives. If the context does not contain the answer,\n"
        "say that it does not, and do not fill the gap from general knowledge.\n\n"
        "<context>\n{context}\n</context>"
    ),
}


def questions(which: str) -> list[dict]:
    """tune: questions used while making changes; holdout: kept back to measure them."""
    all_q = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    holdout = [q for i, q in enumerate(all_q) if i % 3 == 2]
    tune = [q for i, q in enumerate(all_q) if i % 3 != 2]
    return {"tune": tune, "holdout": holdout, "all": all_q}[which]


def spend(add_usd: float = 0.0) -> float:
    total = json.loads(SPEND_FILE.read_text())["usd"] if SPEND_FILE.exists() else 0.0
    total += add_usd
    SPEND_FILE.write_text(json.dumps({"usd": round(total, 6)}))
    return total


def check_budget() -> None:
    if spend() >= BUDGET_USD:
        raise SystemExit(f"Stopped: the trial's model spend reached the {BUDGET_USD} USD cap.")


def ingest(tag: str) -> None:
    with httpx.Client(base_url=RAG, timeout=120) as rag:
        for page in PAGES:
            r = rag.post(
                "/embed",
                data={"file_id": f"{tag}-{page.stem}"},
                files={"file": (page.name, page.read_bytes(), "text/markdown")},
            )
            print(page.name, r.status_code, r.text[:120])


def retrieve(query: str, k: int, tag: str) -> list[dict]:
    with httpx.Client(base_url=RAG, timeout=60) as rag:
        r = rag.post("/query_multiple", json={"query": query, "file_ids": [f"{tag}-{p.stem}" for p in PAGES], "k": k})
        r.raise_for_status()
    chunks = []
    for rank, item in enumerate(r.json(), start=1):
        doc, distance = (item[0], item[1]) if isinstance(item, list) else (item, None)
        meta = doc.get("metadata", {})
        file_id = str(meta.get("file_id", ""))
        chunks.append(
            {
                "rank": rank,
                "chunk_id": f"{file_id}#{rank}",
                "document_id": file_id.removeprefix(f"{tag}-"),
                "text": doc.get("page_content", ""),
                # rag_api returns a cosine distance; TraceroAI shows similarity.
                "final_score": round(1 - distance, 4) if distance is not None else None,
            }
        )
    return chunks


def context_of(chunks: list[dict]) -> str:
    return "\n\n".join(f"[{c['rank']}] ({c['document_id']}) {c['text']}" for c in chunks)


def generate(llm: OpenAI, query: str, context: str, prompt: str) -> tuple[str, int, int]:
    check_budget()
    response = llm.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[{"role": "system", "content": PROMPTS[prompt].format(context=context)}, {"role": "user", "content": query}],
    )
    usage = response.usage
    pin, pout = (usage.prompt_tokens, usage.completion_tokens) if usage else (0, 0)
    spend((pin * PRICE_IN + pout * PRICE_OUT) / 1_000_000)
    return response.choices[0].message.content or "", pin, pout


def run(tag: str, k: int, prompt: str, which: str) -> None:
    settings = get_settings()
    llm = OpenAI(api_key=settings.openai_api_key)
    tracero = TraceroClient(base_url=TRACERO)
    for q in questions(which):
        with tracero.trace(
            q["question"],
            project={"project_id": PROJECT, "environment": "trial"},
            metadata={"trial": "rag_api", "chunking": tag, "top_k": k, "prompt": prompt, "set": which, "page": q["page"]},
        ) as t:
            chunks = retrieve(q["question"], k, tag)
            t.log_retrieval(chunks, strategy="vector", config={"final_top_k": k})
            system = PROMPTS[prompt].format(context=context_of(chunks))
            t.log_prompt(system, version=prompt)
            answer, pin, pout = generate(llm, q["question"], context_of(chunks), prompt)
            t.log_generation(answer, model=MODEL, provider="openai", temperature=0, prompt_tokens=pin, completion_tokens=pout)
    tracero.flush()
    print(f"ran {len(questions(which))} questions; trial spend so far {spend():.4f} USD")


def experiment(which: str, specs: list[str]) -> None:
    settings = get_settings()
    llm = OpenAI(api_key=settings.openai_api_key)
    variants = []
    for spec in specs:
        vid, tag, k, prompt = spec.split(":")
        variants.append(Variant(vid, f"chunks {tag}, top_k {k}, {prompt} prompt", top_k=int(k), extra={"chunking": tag, "prompt": prompt}))

    def _retrieve(query: str, top_k: int, variant: Variant) -> list[dict]:
        return retrieve(query, top_k, variant.extra["chunking"])

    def _generate(query: str, context: str, variant: Variant) -> str:
        return generate(llm, query, context, variant.extra["prompt"])[0]

    dataset = [Case(f"q{i}", q["question"], q["answer"]) for i, q in enumerate(questions(which))]
    result = run_experiment(
        client=TraceroClient(base_url=TRACERO),
        dataset=dataset,
        retrieve=_retrieve,
        generate=_generate,
        variants=variants,
        project_id=PROJECT,
        dataset_name=f"FastAPI docs ({which}, {len(dataset)} questions)",
    )
    for v in result.variants:
        print(f"{v['variant_id']:>10}  {v['name']:<45} passed {v['passed_cases']}/{v['passed_cases'] + v['failed_cases']}")
    print(result.recommendation)
    if result.errors:
        print("errors:", result.errors[:3])
    print(f"trial spend so far {spend():.4f} USD (generation only; judge calls are on the nano model)")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "ingest":
        ingest(args[0])
    elif cmd == "run":
        run(args[0], int(args[1]), args[2], args[3])
    elif cmd == "experiment":
        experiment(args[0], args[1:])
