"""A tiny in-memory knowledge base for the demo RAG app.

Each entry is one retrievable passage. Swap this for your real documents,
a vector DB, etc. — the monitoring code in app.py doesn't change.
"""

DOCUMENTS = [
    {
        "id": "refund_timeline",
        "title": "Refund Policy",
        "source": "refund_policy.md",
        "text": "Refunds are processed within 5 to 7 business days after the request is approved.",
    },
    {
        "id": "refund_method",
        "title": "Refund Policy",
        "source": "refund_policy.md",
        "text": "Refunds are issued to the original payment method used for the purchase, not as account credit.",
    },
    {
        "id": "plans",
        "title": "Product FAQ",
        "source": "product_faq.md",
        "text": "We offer three plans: Free (up to 3 members), Pro (up to 50 members, priority support), and Enterprise (SSO, audit logs, dedicated manager).",
    },
    {
        "id": "upload_size",
        "title": "Product FAQ",
        "source": "product_faq.md",
        "text": "The maximum file upload size is 100 megabytes per file on the Free and Pro plans.",
    },
    {
        "id": "password_reset",
        "title": "Security Policy",
        "source": "security_policy.md",
        "text": "To reset your password, click 'Forgot Password' on the login page; the reset link expires after 30 minutes.",
    },
    {
        "id": "encryption",
        "title": "Security Policy",
        "source": "security_policy.md",
        "text": "Customer data is encrypted in transit using TLS 1.2+ and at rest using AES-256.",
    },
]
