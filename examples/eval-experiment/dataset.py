"""Labeled eval cases for the experiment, answerable from the recovery-agent docs.

A real client would keep their own dataset here (or load a CSV of question,
expected_answer). The last two cases are out-of-knowledge — the correct behavior
is a refusal.
"""

CASES = [
    {"id": "refund_duration", "question": "How long does a refund take?",
     "expected": "Refunds are processed within 5 to 7 business days after the request is approved."},
    {"id": "refund_method", "question": "Where is my refund sent?",
     "expected": "Refunds are issued to the original payment method used for the purchase."},
    {"id": "plans", "question": "What plans do you offer?",
     "expected": "Three plans: Free, Pro, and Enterprise."},
    {"id": "pro_plan", "question": "What does the Pro plan include?",
     "expected": "Unlimited projects and email support with a one-business-day response target."},
    {"id": "upload_size", "question": "What is the maximum file upload size?",
     "expected": "100 megabytes per file."},
    {"id": "password_reset", "question": "How do I reset my password?",
     "expected": "Click Forgot Password on the login page; the reset link expires after 30 minutes."},
    {"id": "encryption", "question": "How is my data encrypted?",
     "expected": "In transit using TLS 1.2+ and at rest using AES-256."},
    {"id": "region_change", "question": "Can I change my workspace region after creating it?",
     "expected": "No, a workspace region cannot be changed after creation; contact support to migrate."},
    {"id": "phone_support", "question": "What is your phone support number?",
     "expected": "I don't know based on the provided context."},
    {"id": "founding_year", "question": "What year was the company founded?",
     "expected": "I don't know based on the provided context."},
]
