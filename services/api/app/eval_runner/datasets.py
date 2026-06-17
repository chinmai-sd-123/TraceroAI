"""Labeled evaluation datasets for the experiment harness.

Each case is a (question, expected_answer) pair — the ground truth the harness
grades a RAG pipeline against. Questions are designed around the playground KB
(see app/api/routes/playground.py) so retrieval can actually find the answers;
the last cases are deliberately out-of-knowledge to test correct refusals.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetCase:
    case_id: str
    question: str
    expected_answer: str


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    name: str
    version: str
    cases: list[DatasetCase]


_SUPPORT_CASES = [
    DatasetCase(
        "refund_duration",
        "How long does a refund take?",
        "Refunds are processed within 5 to 7 business days after the request is approved.",
    ),
    DatasetCase(
        "refund_method",
        "Where is my refund sent?",
        "Refunds are issued to the original payment method used for the purchase.",
    ),
    DatasetCase(
        "plans",
        "What plans do you offer?",
        "There are three plans: Free, Pro, and Enterprise.",
    ),
    DatasetCase(
        "upload_size",
        "What is the maximum file upload size?",
        "The maximum file upload size is 100 megabytes per file.",
    ),
    DatasetCase(
        "password_reset",
        "How do I reset my password?",
        "Click Forgot Password on the login page to reset your password.",
    ),
    DatasetCase(
        "encryption",
        "How is my data protected?",
        "Customer data is encrypted in transit using TLS and at rest using AES-256.",
    ),
    # Out-of-knowledge: the KB has no answer, so the correct behavior is to refuse.
    DatasetCase(
        "free_trial",
        "Do you offer a free trial?",
        "I don't know based on the provided context.",
    ),
    DatasetCase(
        "phone_support",
        "What is your phone support number?",
        "I don't know based on the provided context.",
    ),
]


SUPPORT_FAQ = Dataset(
    dataset_id="support_faq_v1",
    name="Support FAQ",
    version="v1",
    cases=_SUPPORT_CASES,
)


DATASETS: dict[str, Dataset] = {SUPPORT_FAQ.dataset_id: SUPPORT_FAQ}


def get_dataset(dataset_id: str) -> Dataset:
    if dataset_id not in DATASETS:
        available = ", ".join(DATASETS) or "(none)"
        raise KeyError(f"Unknown dataset '{dataset_id}'. Available: {available}")
    return DATASETS[dataset_id]
