import re

from app.schemas.traces import EvaluationResult, TraceIngestRequest


EVALUATOR_NAME = "groundedness"
EVALUATOR_VERSION = "deterministic_v1"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "can",
    "could",
    "did",
    "do",
    "does",
    "how",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "would",
}


def evaluate_groundedness(trace: TraceIngestRequest) -> EvaluationResult:
    answer_terms = extract_terms(trace.generation.answer)
    context = " ".join(chunk.text for chunk in trace.retrieval.chunks)
    context_terms = extract_terms(context)

    if not answer_terms:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            evaluator_version=EVALUATOR_VERSION,
            label="needs_review",
            score=0,
            reason="The answer does not contain enough meaningful terms to evaluate.",
            details={
                "matched_terms": [],
                "missing_terms": [],
            },
        )

    matched_terms = sorted(answer_terms.intersection(context_terms))
    missing_terms = sorted(answer_terms.difference(context_terms))
    score = len(matched_terms) / len(answer_terms)

    if score >= 0.75:
        label = "pass"
    elif score >= 0.45:
        label = "needs_review"
    else:
        label = "fail"

    return EvaluationResult(
        evaluator_name=EVALUATOR_NAME,
        evaluator_version=EVALUATOR_VERSION,
        label=label,
        score=round(score, 3),
        reason=build_reason(label, score, matched_terms, missing_terms),
        details={
            "matched_terms": matched_terms,
            "missing_terms": missing_terms,
            "answer_term_count": len(answer_terms),
            "context_term_count": len(context_terms),
        },
    )


def extract_terms(text: str) -> set[str]:
    terms = set()

    for token in re.findall(r"[a-zA-Z0-9]+", text.lower()):
        if token in STOPWORDS:
            continue

        token = normalize_token(token)

        if len(token) < 3:
            continue

        if token in STOPWORDS:
            continue

        terms.add(token)

    return terms


def normalize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"

    if token.endswith("ed") and len(token) > 4:
        return token[:-2]

    if token.endswith("es") and len(token) > 4:
        return token[:-2]

    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]

    return token


def build_reason(
    label: str,
    score: float,
    matched_terms: list[str],
    missing_terms: list[str],
) -> str:
    matched_preview = ", ".join(matched_terms[:5]) or "none"
    missing_preview = ", ".join(missing_terms[:5]) or "none"

    if label == "pass":
        return (
            f"Most answer terms appear in the retrieved context "
            f"(score={score:.2f}). Matched: {matched_preview}."
        )

    if label == "needs_review":
        return (
            f"Some answer terms are supported, but several are missing "
            f"(score={score:.2f}). Missing: {missing_preview}."
        )

    return (
        f"Many answer terms do not appear in the retrieved context "
        f"(score={score:.2f}). Missing: {missing_preview}."
    )