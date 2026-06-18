"""Labeled eval cases for the recovery-agent KB (docs/*). Used by `python app.py
--eval` to run an experiment via traceroai.eval. The last two are out-of-knowledge
(a refusal is the correct answer)."""

CASES = [
    ("refund_duration", "How long does a refund take?",
     "Refunds are processed within 5 to 7 business days after the request is approved."),
    ("refund_method", "Where is my refund sent?",
     "Refunds are issued to the original payment method used for the purchase."),
    ("plans", "What plans do you offer?",
     "Three plans: Free, Pro, and Enterprise."),
    ("pro_plan", "What does the Pro plan include?",
     "Unlimited projects and email support with a one-business-day response target."),
    ("upload_size", "What is the maximum file upload size?",
     "100 megabytes per file."),
    ("password_reset", "How do I reset my password?",
     "Click Forgot Password on the login page; the reset link expires after 30 minutes."),
    ("encryption", "How is my data encrypted?",
     "In transit using TLS 1.2+ and at rest using AES-256."),
    ("region_change", "Can I change my workspace region after creating it?",
     "No, a workspace region cannot be changed after creation; contact support to migrate."),
    ("phone_support", "What is your phone support number?",
     "I don't know based on the provided context."),
    ("founding_year", "What year was the company founded?",
     "I don't know based on the provided context."),
]
