"""A tiny public 'try it' endpoint for the docs page.

Runs a minimal lexical RAG over a small built-in knowledge base, ingests the
result as a real trace (so it's evaluated + diagnosed by the real pipeline), and
returns the question, answer, retrieved chunks, and diagnosis. No LLM/key needed
— the answer is extractive — so anyone can try it from the public docs page.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
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
from app.services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/v1/playground", tags=["playground"])

# Small built-in KB so the demo is self-contained.
_DOCS = [
    # Refund Policy
    ("Refund Policy", "Refund requests can be submitted within 30 days of purchase."),
    ("Refund Policy", "Refunds are processed within 5 to 7 business days after approval."),
    ("Refund Policy", "Refunds are issued to the original payment method used for the purchase."),
    ("Refund Policy", "Subscription renewals are generally non-refundable after the billing cycle begins."),
    ("Refund Policy", "Enterprise customers should contact their account manager for refund inquiries."),

    # Product FAQ
    ("Product FAQ", "We offer three plans: Free, Pro, and Enterprise."),
    ("Product FAQ", "The maximum file upload size is 100 megabytes per file."),
    ("Product FAQ", "Users can create up to 10 projects on the Free plan."),
    ("Product FAQ", "The Pro plan includes priority support and advanced analytics."),
    ("Product FAQ", "Enterprise plans support custom integrations and dedicated account management."),
    ("Product FAQ", "API access is available on Pro and Enterprise plans."),
    ("Product FAQ", "Unused storage does not roll over between billing cycles."),

    # Security Policy
    ("Security Policy", "To reset your password, click Forgot Password on the login page."),
    ("Security Policy", "Customer data is encrypted in transit using TLS and at rest using AES-256."),
    ("Security Policy", "Multi-factor authentication is available for all user accounts."),
    ("Security Policy", "Password requirements include at least 12 characters and one special symbol."),
    ("Security Policy", "Access logs are retained for 90 days for security monitoring."),
    ("Security Policy", "Regular penetration testing is conducted by third-party security auditors."),

    # Billing
    ("Billing", "Invoices are generated automatically on the first day of each billing cycle."),
    ("Billing", "Customers can update payment methods from the billing settings page."),
    ("Billing", "Failed payments trigger three automatic retry attempts."),
    ("Billing", "Annual subscriptions receive a 15 percent discount compared to monthly plans."),
    ("Billing", "Taxes are applied based on the customer's billing address."),

    # Account Management
    ("Account Management", "Users can change their email address from the profile settings page."),
    ("Account Management", "Account deletion requests are processed within 14 days."),
    ("Account Management", "Deleted accounts cannot be restored after 30 days."),
    ("Account Management", "Users can export their data in CSV or JSON format."),
    ("Account Management", "Team administrators can manage user permissions and roles."),

    # Support
    ("Support", "Support tickets are typically answered within 24 hours on business days."),
    ("Support", "Enterprise customers receive a dedicated support channel."),
    ("Support", "Live chat support is available from 9 AM to 6 PM UTC."),
    ("Support", "Critical incidents are handled according to the priority escalation policy."),
    ("Support", "Users can track ticket status from the support portal."),

    # API Documentation
    ("API Documentation", "API requests require authentication using bearer tokens."),
    ("API Documentation", "Rate limits are set to 1000 requests per hour for Pro users."),
    ("API Documentation", "Enterprise customers can request higher rate limits."),
    ("API Documentation", "API responses are returned in JSON format."),
    ("API Documentation", "Webhook events can be configured from the developer dashboard."),
]

_STOP = {"the", "a", "an", "is", "are", "do", "does", "how", "what", "can", "i", "to", "of", "my", "you", "your"}

def _client_ip(request: Request) -> str:
    # Behind Render's proxy, request.client.host is the proxy. The original
    # visitor IP is the FIRST entry in X-Forwarded-For. Fall back to the
    # socket peer for local/dev where there's no proxy.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"



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
def try_query(payload: PlaygroundRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    # Check rate limit
    if not check_rate_limit(
        bucket="playground",
        identity=_client_ip(request),
        limit=10,
        window_seconds=60
    ):
        raise HTTPException(
            status_code=429,
            detail="Rate limit reached for the live demo — please wait a minute and try again.",
        )

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
