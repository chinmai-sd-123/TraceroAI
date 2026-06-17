"""A configurable RAG pipeline for the experiment harness.

Retrieval is lexical over the same built-in KB the playground uses (no external
deps); generation goes through the configured LLM (Gemini, via the judge client).
The point of the harness is to vary the *config* (top_k, prompt variant, model)
and measure which produces better answers — so those knobs live in VariantConfig.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from openai import OpenAI

from app.core.config import get_settings

# Same KB as the playground, so a curated dataset can be answered from it.
_DOCS: list[tuple[str, str]] = [
    ("Refund Policy", "Refunds are processed within 5 to 7 business days after the request is approved."),
    ("Refund Policy", "Refunds are issued to the original payment method used for the purchase."),
    ("Product FAQ", "We offer three plans: Free, Pro, and Enterprise."),
    ("Product FAQ", "The maximum file upload size is 100 megabytes per file."),
    ("Security Policy", "To reset your password, click Forgot Password on the login page."),
    ("Security Policy", "Customer data is encrypted in transit using TLS and at rest using AES-256."),
]

_STOP = {"the", "a", "an", "is", "are", "do", "does", "how", "what", "can", "i",
         "to", "of", "my", "you", "your", "where", "when", "why"}

# Two prompt variants — an experiment knob. v2 is stricter about refusing.
PROMPT_VARIANTS = {
    "v1": (
        "Answer the question using the context below. Cite sources like [1].\n\n"
        "Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    ),
    "v2": (
        "Answer the question using ONLY the context below. Cite sources like [1]. "
        "If the context does not contain the answer, reply exactly: "
        "\"I don't know based on the provided context.\"\n\n"
        "Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    ),
}


@dataclass(frozen=True)
class VariantConfig:
    """One pipeline configuration to evaluate."""

    variant_id: str
    name: str
    top_k: int = 3
    prompt_variant: str = "v2"
    model: str | None = None  # None -> use the configured judge_model

    def as_dict(self) -> dict:
        return {
            "top_k": self.top_k,
            "prompt_variant": self.prompt_variant,
            "model": self.model or get_settings().judge_model,
        }


@dataclass
class RagResult:
    answer: str
    chunks: list[dict] = field(default_factory=list)
    latency_ms: int = 0
    error: str | None = None


def _normalize(token: str) -> str:
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _terms(text: str) -> set[str]:
    return {
        _normalize(t)
        for t in re.findall(r"[a-z0-9]+", text.lower())
        if len(t) >= 3 and t not in _STOP
    }


def retrieve(question: str, top_k: int) -> list[dict]:
    """Lexical top-k retrieval over the KB. Returns chunks in trace-chunk shape."""
    q = _terms(question)
    scored = sorted(
        (
            (title, text, (len(q & _terms(text)) / len(q) if q else 0.0))
            for title, text in _DOCS
        ),
        key=lambda x: x[2],
        reverse=True,
    )[:top_k]
    return [
        {
            "rank": i + 1,
            "chunk_id": f"kb_{i + 1}",
            "document_title": title,
            "source": f"{title.lower().replace(' ', '_')}.md",
            "final_score": round(score, 3),
            "text": text,
        }
        for i, (title, text, score) in enumerate(scored)
    ]


def _build_prompt(question: str, chunks: list[dict], prompt_variant: str) -> str:
    context = "\n\n".join(f"[{c['rank']}] {c['text']}" for c in chunks) or "(no context)"
    template = PROMPT_VARIANTS.get(prompt_variant, PROMPT_VARIANTS["v2"])
    return template.format(context=context, question=question)


def run_rag(question: str, config: VariantConfig) -> RagResult:
    """Retrieve + generate for one question under one config.

    Generation failures (no key, 429) degrade to an extractive fallback so a run
    always completes — mirroring the rest of the system's fail-open behavior.
    """
    import time

    start = time.perf_counter()
    chunks = retrieve(question, config.top_k)
    prompt = _build_prompt(question, chunks, config.prompt_variant)

    settings = get_settings()
    model = config.model or settings.judge_model

    if not settings.openai_api_key:
        answer = chunks[0]["text"] if chunks else "I don't know based on the provided context."
        return RagResult(answer=answer, chunks=chunks,
                         latency_ms=int((time.perf_counter() - start) * 1000),
                         error="no_api_key_extractive_fallback")

    try:
        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.judge_base_url)
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = completion.choices[0].message.content or ""
        error = None
    except Exception as exc:  # 429 / network / etc.
        answer = chunks[0]["text"] if chunks else "I don't know based on the provided context."
        error = f"{type(exc).__name__}: {str(exc)[:120]}"

    return RagResult(
        answer=answer.strip(),
        chunks=chunks,
        latency_ms=int((time.perf_counter() - start) * 1000),
        error=error,
    )
