"""Field trial 2: LightRAG, instrumented with TraceroAI.

LightRAG (MIT, github.com/HKUDS/LightRAG) builds a knowledge graph from documents and
answers from entities, relationships and chunks. This trial indexes six pages of
LightRAG's own 2025-2026 documentation (written after gpt-4o-mini's training data, so
the model can't answer from memory), asks questions with the official OpenAI setup
(gpt_4o_mini_complete, openai_embed), and traces every run to a local TraceroAI stack.

Run with LightRAG's virtualenv, OPENAI_API_KEY set, TraceroAI on :8000.

    python trial_lightrag.py index                                  # build the graph (the costly step)
    python trial_lightrag.py run <mode> <top_k> <chunk_top_k> <set>  # trace every question in a set
    python trial_lightrag.py experiment <set> <id:mode:top_k:chunk_top_k> ...
"""

from __future__ import annotations

import asyncio
import functools
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = Path(__file__).resolve().parents[2]  # the TraceroAI checkout
# The LightRAG checkout sits beside this script; don't let its folder shadow the
# installed package.
sys.path = [p for p in sys.path if Path(p or ".").resolve() != HERE.resolve()]
sys.path.insert(0, str(REPO / "sdks" / "python"))

from lightrag import LightRAG, QueryParam  # noqa: E402
from lightrag.llm.openai import gpt_4o_mini_complete, openai_embed  # noqa: E402
from lightrag.utils import TokenTracker  # noqa: E402
from traceroai import TraceroClient  # noqa: E402
from traceroai.eval import Case, Variant, run_experiment  # noqa: E402

TRACERO = "http://localhost:8000"
PROJECT = "trial-lightrag"
CORPUS = HERE / "corpus"  # fetched by fetch_corpus.sh
WORKDIR = HERE / "results" / "index"
MODEL = "gpt-4o-mini"
PRICE_IN, PRICE_OUT = 0.15, 0.60  # USD per million tokens, gpt-4o-mini list price
BUDGET_USD = 0.50
SPEND_FILE = HERE / "results" / "spend.json"
EMBED_PRICE = 0.02  # text-embedding-3-small, per million tokens (counted as an estimate)

tracker = TokenTracker()


def spend_so_far() -> float:
    return json.loads(SPEND_FILE.read_text())["usd"] if SPEND_FILE.exists() else 0.0


def record_spend() -> float:
    usd = (tracker.prompt_tokens * PRICE_IN + tracker.completion_tokens * PRICE_OUT) / 1_000_000
    total = spend_so_far() + usd
    SPEND_FILE.write_text(json.dumps({"usd": round(total, 6)}))
    tracker.reset()
    return total


def check_budget() -> None:
    if spend_so_far() >= BUDGET_USD:
        raise SystemExit(f"Stopped: the trial's model spend reached the {BUDGET_USD} USD cap.")


async def make_rag() -> LightRAG:
    WORKDIR.mkdir(exist_ok=True)
    rag = LightRAG(
        working_dir=str(WORKDIR),
        embedding_func=openai_embed,
        llm_model_func=functools.partial(gpt_4o_mini_complete, token_tracker=tracker),
    )
    await rag.initialize_storages()
    return rag


def questions(which: str) -> list[dict]:
    all_q = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    holdout = [q for i, q in enumerate(all_q) if i % 3 == 2]
    tune = [q for i, q in enumerate(all_q) if i % 3 != 2]
    return {"tune": tune, "holdout": holdout, "all": all_q}[which]


async def index() -> None:
    check_budget()
    rag = await make_rag()
    pages = sorted(CORPUS.glob("*.md"))
    await rag.ainsert([p.read_text(encoding="utf-8") for p in pages], file_paths=[p.name for p in pages])
    print(f"indexed {len(pages)} pages; tokens in={tracker.prompt_tokens} out={tracker.completion_tokens}")
    print(f"trial spend so far {record_spend():.4f} USD (LLM only; embeddings are a fraction of a cent)")
    await rag.finalize_storages()


def param(mode: str, top_k: int, chunk_top_k: int) -> QueryParam:
    return QueryParam(mode=mode, top_k=top_k, chunk_top_k=chunk_top_k, enable_rerank=False)  # type: ignore[arg-type]


async def ask(rag: LightRAG, question: str, mode: str, top_k: int, chunk_top_k: int) -> tuple[str, list[dict]]:
    check_budget()
    result = await rag.aquery_llm(question, param=param(mode, top_k, chunk_top_k))
    data = result.get("data") or {}
    chunks = [
        {
            "rank": rank,
            "chunk_id": c.get("chunk_id") or f"chunk-{rank}",
            "document_id": c.get("file_path"),
            "text": c.get("content") or "",
        }
        for rank, c in enumerate(data.get("chunks") or [], start=1)
    ]
    answer = ((result.get("llm_response") or {}).get("content")) or ""
    return answer, chunks


async def run(mode: str, top_k: int, chunk_top_k: int, which: str) -> None:
    rag = await make_rag()
    tracero = TraceroClient(base_url=TRACERO)
    for q in questions(which):
        with tracero.trace(
            q["question"],
            project={"project_id": PROJECT, "environment": "trial"},
            metadata={"trial": "lightrag", "mode": mode, "top_k": top_k, "chunk_top_k": chunk_top_k, "set": which, "page": q["page"]},
        ) as t:
            before_in, before_out = tracker.prompt_tokens, tracker.completion_tokens
            answer, chunks = await ask(rag, q["question"], mode, top_k, chunk_top_k)
            t.log_retrieval(chunks, strategy=f"lightrag-{mode}", config={"final_top_k": chunk_top_k})
            t.log_prompt("LightRAG's built-in RAG response prompt", version=f"lightrag-{mode}")
            t.log_generation(
                answer or "[no answer]",
                model=MODEL,
                provider="openai",
                prompt_tokens=tracker.prompt_tokens - before_in,
                completion_tokens=tracker.completion_tokens - before_out,
            )
    tracero.flush()
    print(f"ran {len(questions(which))} questions; trial spend so far {record_spend():.4f} USD")
    await rag.finalize_storages()


async def experiment(which: str, specs: list[str]) -> None:
    rag = await make_rag()
    loop = asyncio.get_running_loop()
    variants = []
    for spec in specs:
        vid, mode, top_k, chunk_top_k = spec.split(":")
        variants.append(Variant(vid, f"{mode}, top_k {top_k}, chunk_top_k {chunk_top_k}", top_k=int(top_k), extra={"mode": mode, "chunk_top_k": int(chunk_top_k)}))
    answers: dict[tuple[str, str], str] = {}
    usage: dict[tuple[str, str], dict] = {}

    # run_experiment is synchronous: precompute each variant's answers, then hand
    # them over. retrieve() returns the chunks LightRAG used; generate() returns
    # LightRAG's own answer for that variant.
    chunks_by: dict[tuple[str, str], list[dict]] = {}
    for v in variants:
        for q in questions(which):
            before_in, before_out = tracker.prompt_tokens, tracker.completion_tokens
            answer, chunks = await ask(rag, q["question"], v.extra["mode"], v.top_k, v.extra["chunk_top_k"])
            answers[(v.variant_id, q["question"])] = answer
            # Cached LightRAG responses report no tokens; run with a fresh index for full counts.
            usage[(v.variant_id, q["question"])] = {
                "prompt_tokens": tracker.prompt_tokens - before_in,
                "completion_tokens": tracker.completion_tokens - before_out,
                "model": MODEL,
            }
            chunks_by[(v.variant_id, q["question"])] = chunks

    def _retrieve(query: str, top_k: int, variant: Variant) -> list[dict]:
        return chunks_by[(variant.variant_id, query)]

    def _generate(query: str, context: str, variant: Variant) -> tuple[str, dict]:
        # (answer, usage): the experiment then reports tokens and cost per variant.
        return answers[(variant.variant_id, query)], usage[(variant.variant_id, query)]

    dataset = [Case(f"q{i}", q["question"], q["answer"]) for i, q in enumerate(questions(which))]
    result = await loop.run_in_executor(
        None,
        lambda: run_experiment(
            client=TraceroClient(base_url=TRACERO),
            dataset=dataset,
            retrieve=_retrieve,
            generate=_generate,
            variants=variants,
            project_id=PROJECT,
            dataset_name=f"LightRAG docs ({which}, {len(dataset)} questions)",
        ),
    )
    for v in result.variants:
        print(f"{v['variant_id']:>10}  {v['name']:<40} passed {v['passed_cases']}/{v['passed_cases'] + v['failed_cases']}")
    if result.errors:
        print("errors:", result.errors[:3])
    print(f"trial spend so far {record_spend():.4f} USD")
    await rag.finalize_storages()


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "index":
        asyncio.run(index())
    elif cmd == "run":
        asyncio.run(run(args[0], int(args[1]), int(args[2]), args[3]))
    elif cmd == "experiment":
        asyncio.run(experiment(args[0], args[1:]))
