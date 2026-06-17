"""A small in-memory knowledge base for the LangChain RAG example.

Real apps load documents from files / a vector DB; we inline a few so the example
runs with no external data. Each document is a (title, text) pair that gets
embedded into an in-memory FAISS-free vector store (see rag_chain.py).
"""

from __future__ import annotations

DOCUMENTS: list[dict[str, str]] = [
    {
        "id": "refund_policy",
        "title": "Refund Policy",
        "text": (
            "Refunds are processed within 5 to 7 business days after the request "
            "is approved. Refunds are issued to the original payment method used "
            "for the purchase. Subscriptions can be refunded within 14 days of renewal."
        ),
    },
    {
        "id": "plans",
        "title": "Plans & Pricing",
        "text": (
            "We offer three plans: Free, Pro, and Enterprise. The Free plan includes "
            "1 project and community support. Pro adds unlimited projects and email "
            "support. Enterprise adds SSO, audit logs, and a dedicated success manager."
        ),
    },
    {
        "id": "limits",
        "title": "Usage Limits",
        "text": (
            "The maximum file upload size is 100 megabytes per file. Free accounts "
            "are limited to 1,000 API requests per day; Pro accounts to 100,000."
        ),
    },
    {
        "id": "security",
        "title": "Security",
        "text": (
            "Customer data is encrypted in transit using TLS 1.2+ and at rest using "
            "AES-256. To reset your password, click 'Forgot Password' on the login "
            "page. We are SOC 2 Type II certified."
        ),
    },
    {
        "id": "regions",
        "title": "Data Residency",
        "text": (
            "Workspaces can be created in US or EU regions. A workspace region cannot "
            "be changed after creation; to move regions, contact support to migrate."
        ),
    },
]
