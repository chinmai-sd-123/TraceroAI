"""A tiny public 'try it' endpoint for the docs page.

Runs a minimal lexical RAG over a small built-in knowledge base, ingests the
result as a real trace (so it's evaluated + diagnosed by the real pipeline), and
returns the question, answer, retrieved chunks, and diagnosis. No LLM/key needed
— the answer is extractive — so anyone can try it from the public docs page.
"""

from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.evaluators.deep_groundedness import evaluate_deep_groundedness
from app.evaluators.deep_relevance import (
    evaluate_deep_answer_relevance,
    evaluate_deep_context_relevance,
)
from app.evaluators.diagnosis import diagnose_from_deep, is_refusal
from app.schemas.traces import TraceIngestRequest
from app.services.llm_judge import OpenAIJudge
from app.services.quick_evaluation import run_quick_evaluation
from app.services.trace_repository import TraceRepository
from fastapi import Depends

router = APIRouter(prefix="/v1/playground", tags=["playground"])

# Small built-in KB so the demo is self-contained.
_DOCS = [
    ("Refund Policy", "Refunds are processed within 5 to 7 business days after the request is approved."),
    ("Refund Policy", "Refunds are issued to the original payment method used for the purchase."),
    ("Product FAQ", "We offer three plans: Free, Pro, and Enterprise."),
    ("Product FAQ", "The maximum file upload size is 100 megabytes per file."),
    ("Security Policy", "To reset your password, click Forgot Password on the login page."),
    ("Security Policy", "Customer data is encrypted in transit using TLS and at rest using AES-256."),
]

_STOP = {"the", "a", "an", "is", "are", "do", "does", "how", "what", "can", "i", "to", "of", "my", "you", "your"}


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


class PlaygroundRequest(BaseModel):
    question: str


@router.post("")
def try_query(payload: PlaygroundRequest, db: Session = Depends(get_db)) -> dict:
    query = payload.question.strip()
    q = _terms(query)

    scored = sorted(
        ((title, text, (len(q & _terms(text)) / len(q) if q else 0.0)) for title, text in _DOCS),
        key=lambda x: x[2],
        reverse=True,
    )[:3]

    chunks = [
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

    top_score = scored[0][2] if scored else 0.0
    answer = scored[0][1] if top_score > 0 else "I don't know based on the provided context."

    trace = TraceIngestRequest(
        query={"original": query},
        retrieval={"strategy": "lexical_top_k", "config": {"final_top_k": 3}, "chunks": chunks},
        generation={"model": "extractive-demo", "answer": answer},
        project={"project_id": "playground"},
        metadata={"source": "docs_playground"},
    )
    trace = run_quick_evaluation(trace)

    # The deterministic term-overlap checks are brittle on short queries. If an
    # LLM judge is configured, run it synchronously and re-diagnose from its
    # semantic verdicts — this is the flagship quick→deep correction, live. Any
    # failure (no key, API error) silently keeps the deterministic diagnosis so
    # the public demo never breaks.
    judged_by = "deterministic"
    settings = get_settings()
    if settings.deep_eval_enabled and settings.openai_api_key:
        try:
            judge = OpenAIJudge()
            deep_results = [
                evaluate_deep_context_relevance(trace, judge),
                evaluate_deep_groundedness(trace, judge),
                evaluate_deep_answer_relevance(trace, judge),
            ]
            trace.evaluations.deep = deep_results
            refused = not trace.generation.answered or is_refusal(answer)
            deep_diagnosis = diagnose_from_deep(deep_results, refused=refused)
            if deep_diagnosis is not None:
                trace.diagnosis = deep_diagnosis
                judged_by = "llm_judge"
        except Exception:
            pass  # keep the deterministic diagnosis

    TraceRepository(db).save(trace)

    return {
        "trace_id": str(trace.trace_id),
        "query": query,
        "answer": answer,
        "judged_by": judged_by,
        "diagnosis": {"label": trace.diagnosis.label, "reason": trace.diagnosis.reason},
        "chunks": [{"title": c["document_title"], "score": c["final_score"], "text": c["text"]} for c in chunks],
    }
