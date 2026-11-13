"""Golden cases built from a small knowledge base, labelled by construction.

Each fact below is turned into six traces. Their expected diagnoses follow from
how each trace is put together, using the definitions in the README:

  healthy          context: the fact + a neighbouring fact from the same document
                   answer:  a paraphrase of the fact               -> healthy_answer
  unsupported      same context; the paraphrase plus an invented claim
                                                                    -> unsupported_claim
  retrieval_miss   context: two facts from other documents
                   answer:  the correct answer, unsupported by that context
                                                                    -> retrieval_miss
  correct_refusal  context: two facts from other documents; answer: a refusal
                                                                    -> correct_refusal
  wrong_refusal    context: the fact + neighbour; answer: a refusal -> wrong_answer
  off_target       context: the fact + neighbour; answer: the neighbour's content,
                   grounded but not what was asked                  -> wrong_answer

The labels are the author's (constructed, not observed in production). Review
them like code: a case whose construction doesn't match its label is a bug in
this file, not in the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    key: str
    document: str
    text: str  # the chunk that answers the question
    question: str
    answer: str  # a correct paraphrase of `text`
    invented: str  # a plausible claim the documents don't support
    neighbour: str  # same document, related, but doesn't answer the question
    neighbour_answer: str  # a paraphrase of `neighbour`


FACTS: tuple[Fact, ...] = (
    Fact(
        "refund_window", "Refund Policy",
        "Refund requests can be submitted within 30 days of purchase.",
        "How long do I have to ask for a refund?",
        "You can request a refund up to 30 days after you buy.",
        "Requests made after that are still accepted with a 10 percent fee.",
        "Refunds are issued to the original payment method used for the purchase.",
        "Refunds go back to the payment method you originally used.",
    ),
    Fact(
        "refund_speed", "Refund Policy",
        "Refunds are processed within 5 to 7 business days after approval.",
        "How long does it take to get my money back once a refund is approved?",
        "Approved refunds are processed in 5 to 7 business days.",
        "Customers in Europe receive their refunds within 24 hours.",
        "Refund requests can be submitted within 30 days of purchase.",
        "You can ask for a refund within 30 days of buying.",
    ),
    Fact(
        "renewal_refund", "Refund Policy",
        "Subscription renewals are generally non-refundable after the billing cycle begins.",
        "Can I get a refund on a renewal after the new billing cycle has started?",
        "Generally no: renewals aren't refundable once the billing cycle begins.",
        "You can, however, get store credit for the unused months.",
        "Enterprise customers should contact their account manager for refund inquiries.",
        "Enterprise customers should ask their account manager about refunds.",
    ),
    Fact(
        "plans", "Product FAQ",
        "We offer three plans: Free, Pro, and Enterprise.",
        "Which plans are available?",
        "There are three plans: Free, Pro and Enterprise.",
        "A Student plan is also available at half the Pro price.",
        # (A neighbour naming the plans would partly answer the question.)
        "Unused storage does not roll over between billing cycles.",
        "Unused storage doesn't carry over to the next billing cycle.",
    ),
    Fact(
        "upload_size", "Product FAQ",
        "The maximum file upload size is 100 megabytes per file.",
        "What's the largest file I can upload?",
        "Each file can be up to 100 MB.",
        "Enterprise accounts can upload files of up to 5 GB.",
        "Users can create up to 10 projects on the Free plan.",
        "The Free plan allows up to 10 projects.",
    ),
    Fact(
        "api_free_plan", "Product FAQ",
        "API access is available on Pro and Enterprise plans.",
        "Does the Free plan include API access?",
        "No, the API is only available on the Pro and Enterprise plans.",
        "Free users get 100 API calls per month as a trial.",
        "The Pro plan includes priority support and advanced analytics.",
        "Pro comes with priority support and advanced analytics.",
    ),
    Fact(
        "password_reset", "Security Policy",
        "To reset your password, click Forgot Password on the login page.",
        "How do I reset my password?",
        "Use the Forgot Password link on the login page.",
        "You will also need to confirm the reset by calling support.",
        "Multi-factor authentication is available for all user accounts.",
        "Every account can turn on multi-factor authentication.",
    ),
    Fact(
        "encryption", "Security Policy",
        "Customer data is encrypted in transit using TLS and at rest using AES-256.",
        "Is my data encrypted at rest?",
        "Yes, stored data is encrypted with AES-256.",
        "Encryption keys are rotated every 24 hours by a dedicated hardware module.",
        "Access logs are retained for 90 days for security monitoring.",
        "Access logs are kept for 90 days.",
    ),
    Fact(
        "password_rules", "Security Policy",
        "Password requirements include at least 12 characters and one special symbol.",
        "What are the password rules?",
        "Passwords need at least 12 characters, including one special symbol.",
        "Passwords also expire every 30 days.",
        "Regular penetration testing is conducted by third-party security auditors.",
        "Outside security auditors run regular penetration tests.",
    ),
    Fact(
        "invoices", "Billing",
        "Invoices are generated automatically on the first day of each billing cycle.",
        "When are invoices created?",
        "An invoice is generated automatically at the start of each billing cycle.",
        "Paper copies of every invoice are also mailed to the billing address.",
        "Customers can update payment methods from the billing settings page.",
        "Payment methods can be changed on the billing settings page.",
    ),
    Fact(
        "failed_payment", "Billing",
        "Failed payments trigger three automatic retry attempts.",
        "What happens if my payment fails?",
        "The payment is retried automatically up to three times.",
        "After the third failure the account is deleted immediately.",
        "Taxes are applied based on the customer's billing address.",
        "Taxes depend on your billing address.",
    ),
    Fact(
        "annual_discount", "Billing",
        "Annual subscriptions receive a 15 percent discount compared to monthly plans.",
        "Is there a discount for paying yearly?",
        "Yes, paying annually saves 15 percent compared with monthly billing.",
        "Paying two years upfront saves 30 percent.",
        "Invoices are generated automatically on the first day of each billing cycle.",
        "Invoices are created automatically when each billing cycle starts.",
    ),
    Fact(
        "account_deletion", "Account Management",
        "Account deletion requests are processed within 14 days.",
        "How long does it take to delete my account?",
        "Deletion requests are handled within 14 days.",
        "Deleted data is kept in backups for five years.",
        "Users can export their data in CSV or JSON format.",
        "You can export your data as CSV or JSON.",
    ),
    Fact(
        "export_formats", "Account Management",
        "Users can export their data in CSV or JSON format.",
        "In which formats can I export my data?",
        "Exports are available as CSV or JSON.",
        "PDF and Excel exports are also supported.",
        "Users can change their email address from the profile settings page.",
        "Your email address can be changed on the profile settings page.",
    ),
    Fact(
        "roles", "Account Management",
        "Team administrators can manage user permissions and roles.",
        "Who can change a teammate's role?",
        "Team administrators manage roles and permissions.",
        "Any member can promote themselves to administrator.",
        "Deleted accounts cannot be restored after 30 days.",
        "A deleted account can't be restored after 30 days.",
    ),
    Fact(
        "support_response", "Support",
        "Support tickets are typically answered within 24 hours on business days.",
        "How quickly does support reply?",
        "Usually within 24 hours on business days.",
        "Weekend tickets are answered within one hour.",
        "Users can track ticket status from the support portal.",
        "Ticket status can be followed in the support portal.",
    ),
    Fact(
        "chat_hours", "Support",
        "Live chat support is available from 9 AM to 6 PM UTC.",
        "What are the live chat hours?",
        "Live chat runs from 9 AM to 6 PM UTC.",
        "Chat is open around the clock for Pro customers.",
        "Enterprise customers receive a dedicated support channel.",
        "Enterprise customers get their own support channel.",
    ),
    Fact(
        "rate_limit", "API Documentation",
        "Rate limits are set to 1000 requests per hour for Pro users.",
        "What is the API rate limit on the Pro plan?",
        "Pro users can make 1000 requests per hour.",
        "Unused requests roll over to the next hour.",
        "API responses are returned in JSON format.",
        "The API responds in JSON.",
    ),
)

# Rotated so no single phrasing dominates the refusal cases.
REFUSALS = (
    "I don't know based on the provided context.",
    "The provided documents don't mention that.",
    "I couldn't find information about that in the context.",
    "There is no information about this in the provided context.",
)


def _chunk(rank: int, chunk_id: str, document: str, text: str) -> dict:
    return {
        "rank": rank,
        "chunk_id": chunk_id,
        "document_title": document,
        "text": text,
    }


def _trace(question: str, chunks: list[dict], answer: str) -> dict:
    return {
        "query": {"original": question},
        "retrieval": {"strategy": "constructed", "chunks": chunks},
        "generation": {"model": "constructed", "answer": answer},
    }


def _unrelated(index: int) -> tuple[Fact, Fact]:
    """Two facts from other documents, chosen deterministically."""
    fact = FACTS[index]
    picks = [FACTS[(index + offset) % len(FACTS)] for offset in (9, 10)]
    assert all(p.document != fact.document for p in picks), fact.key
    return picks[0], picks[1]


def build_cases() -> list[dict]:
    cases: list[dict] = []
    for index, fact in enumerate(FACTS):
        relevant = [
            _chunk(1, f"{fact.key}_1", fact.document, fact.text),
            _chunk(2, f"{fact.key}_2", fact.document, fact.neighbour),
        ]
        first, second = _unrelated(index)
        unrelated = [
            _chunk(1, f"{first.key}_1", first.document, first.text),
            _chunk(2, f"{second.key}_1", second.document, second.text),
        ]
        refusal = REFUSALS[index % len(REFUSALS)]
        variants = [
            ("healthy", relevant, fact.answer, "healthy_answer"),
            ("unsupported", relevant, f"{fact.answer} {fact.invented}", "unsupported_claim"),
            ("retrieval_miss", unrelated, fact.answer, "retrieval_miss"),
            ("correct_refusal", unrelated, refusal, "correct_refusal"),
            ("wrong_refusal", relevant, refusal, "wrong_answer"),
            ("off_target", relevant, fact.neighbour_answer, "wrong_answer"),
        ]
        for name, chunks, answer, expected in variants:
            cases.append(
                {
                    "case_id": f"constructed_{fact.key}_{name}",
                    "expected_diagnosis": expected,
                    "construction": name,
                    "trace": _trace(fact.question, chunks, answer),
                }
            )
    return cases
