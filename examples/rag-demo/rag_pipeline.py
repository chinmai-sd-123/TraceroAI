"""A minimal, dependency-free RAG pipeline for generating TraceroAI demo traces.

Hand-rolled on purpose: lexical (term-overlap) retrieval over a small markdown
knowledge base, a grounded prompt, and an extractive baseline generator. The
point of TraceroAI is to debug RAG internals, so the internals are visible here
rather than hidden behind a framework. Swap `generate` for a real LLM call when
one is available.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DOCUMENTS_DIR = Path(__file__).parent / "documents"

STOPWORDS = {
    "the", "a", "an", "and", "or", "is", "are", "do", "does", "how", "what",
    "can", "i", "to", "of", "my", "you", "your", "for", "on", "in", "it",
}


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    document_title: str
    section: str
    source: str
    text: str


def _normalize(token: str) -> str:
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        if len(token) < 3 or token in STOPWORDS:
            continue
        terms.add(_normalize(token))
    return terms


def load_chunks() -> list[Chunk]:
    """Load each `## Section` block of every markdown doc as one chunk."""
    chunks: list[Chunk] = []
    for path in sorted(DOCUMENTS_DIR.glob("*.md")):
        doc_id = path.stem
        title = doc_id.replace("_", " ").title()
        for block in path.read_text(encoding="utf-8").split("\n\n"):
            lines = [line for line in block.strip().splitlines() if line.strip()]
            if not lines or lines[0].startswith("# ") and not lines[0].startswith("## "):
                continue  # skip blank blocks and the top-level title
            if lines[0].startswith("## "):
                section, body = lines[0][3:].strip(), " ".join(lines[1:]).strip()
            else:
                section, body = "General", " ".join(lines).strip()
            if body:
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc_id}_{len(chunks) + 1}",
                        document_id=doc_id,
                        document_title=title,
                        section=section,
                        source=path.name,
                        text=body,
                    )
                )
    return chunks


def retrieve(query: str, chunks: list[Chunk], top_k: int = 3) -> list[tuple[Chunk, float]]:
    """Score every chunk by query-term overlap and return the top_k."""
    query_terms = _terms(query)
    scored = [
        (chunk, round(len(query_terms & _terms(chunk.text)) / len(query_terms), 3) if query_terms else 0.0)
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]


def build_prompt(query: str, retrieved: list[tuple[Chunk, float]]) -> str:
    context = "\n\n".join(f"[{i + 1}] {chunk.text}" for i, (chunk, _) in enumerate(retrieved))
    return (
        "Answer the question using ONLY the context below. Cite sources like [1].\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\nAnswer:"
    )


def generate(query: str, retrieved: list[tuple[Chunk, float]]) -> str:
    """Extractive baseline generator (no LLM required).

    Returns the most relevant chunk as the answer. Replace this with an LLM call
    (e.g. OpenAI) when one is configured; the rest of the pipeline is unchanged.
    """
    if not retrieved or retrieved[0][1] == 0.0:
        return "I'm sorry, I don't have information to answer that."
    return retrieved[0][0].text