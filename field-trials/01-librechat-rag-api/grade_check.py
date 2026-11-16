"""Compare two answer-correctness graders against hand labels.

Grades the 30 held-back answers from field trial 1 with the current grader and a
candidate, twice each, and reports agreement with hand labels and run-to-run
agreement. Run from services/api (key from TraceroAI's settings, never printed).
"""

import json
import sys
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field

sys.path.insert(0, ".")
from app.core.config import get_settings  # noqa: E402
from app.services.llm_judge import CORRECTNESS_PROMPT  # noqa: E402

HERE = Path(__file__).parent

# Hand labels for holdout-graded.json (baseline 0-9, grounded 10-19, smaller 20-29),
# read against the full question and expected answer. Two answers are wrong:
# 7 (baseline) opens with a wrong rule ("position in the URL"), and 29 (smaller)
# leaves out how tokenUrl is interpreted, which the question asks.
HAND = [True] * 30
HAND[7] = False
HAND[29] = False


class OldVerdict(BaseModel):
    correct: bool
    reason: str


CANDIDATE_PROMPT = (
    "You grade a RAG ANSWER against a reference EXPECTED answer for a QUESTION.\n"
    "First list the main fact(s) in EXPECTED that directly answer the QUESTION. "
    "Examples, file names, asides and secondary details in EXPECTED are not main facts.\n"
    "Then decide:\n"
    "- correct=true if the ANSWER states every main fact (in any wording) and contradicts "
    "nothing in EXPECTED. Extra correct detail is fine. Leaving out secondary details or "
    "examples is fine.\n"
    "- correct=false if it misses or gets wrong a main fact, contradicts EXPECTED, or is "
    "vague where a specific answer was expected.\n"
    "- If EXPECTED is a refusal ('I don't know...'), a refusal is correct and a confident "
    "made-up answer is incorrect.\n"
    "Write the reason before the verdict, in one or two sentences."
)


FOCUSED_PROMPT = (
    "You grade a RAG ANSWER against a reference EXPECTED answer for a QUESTION.\n"
    "First list the main fact(s): what the QUESTION actually asks for, as EXPECTED answers it. "
    "Anything in EXPECTED that the QUESTION does not ask about (examples, file names, asides, "
    "related rules) is not a main fact.\n"
    "Then decide:\n"
    "- correct=true if the ANSWER states every main fact (in any wording) and contradicts "
    "nothing in EXPECTED. Extra correct detail is fine.\n"
    "- correct=false if it misses or gets wrong a main fact, states a rule that contradicts "
    "EXPECTED (even if it later corrects itself), or is vague where a specific answer was expected.\n"
    "- If EXPECTED is a refusal ('I don't know...'), a refusal is correct and a confident "
    "made-up answer is incorrect.\n"
    "Write the reason before the verdict, in one or two sentences."
)


class NewVerdict(BaseModel):
    main_facts: list[str] = Field(description="Facts in EXPECTED that directly answer the question.")
    reason: str
    correct: bool


def grade(client: OpenAI, model: str, prompt: str, schema: type[BaseModel], case: dict) -> bool:
    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"QUESTION:\n{case['question']}\n\nEXPECTED:\n{case['expected_answer']}\n\nACTUAL:\n{case['actual_answer']}",
            },
        ],
        response_format=schema,
    )
    parsed = completion.choices[0].message.parsed
    assert parsed is not None
    return bool(parsed.correct)  # type: ignore[attr-defined]


def main() -> None:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.judge_base_url or None)
    model = settings.judge_model
    cases = json.loads((HERE / "results" / "holdout-graded.json").read_text(encoding="utf-8"))
    recorded = [bool(c["passed"]) for c in cases]
    print(f"model={model}; recorded run (old grader, via the API): agrees with hand labels on "
          f"{sum(a == b for a, b in zip(recorded, HAND))}/30")
    for name, prompt, schema in [
        ("old", CORRECTNESS_PROMPT, OldVerdict),
        ("facts-first", CANDIDATE_PROMPT, NewVerdict),
        ("question-focused", FOCUSED_PROMPT, NewVerdict),
    ]:
        runs = [[grade(client, model, prompt, schema, c) for c in cases] for _ in range(2)]
        agree = [sum(a == b for a, b in zip(r, HAND)) for r in runs]
        stable = sum(a == b for a, b in zip(runs[0], runs[1]))
        print(f"{name}: agrees with hand labels {agree[0]}/30 and {agree[1]}/30; same verdict in both runs {stable}/30")


if __name__ == "__main__":
    main()
