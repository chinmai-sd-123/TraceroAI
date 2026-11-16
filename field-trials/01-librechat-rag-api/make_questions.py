"""Draft question/answer pairs for a trial corpus, and keep only verifiable ones.

A small model writes pairs per page, each with a verbatim supporting quote. A pair
is kept only if its quote really appears in the page (whitespace-normalised), so
every expected answer is backed by the source. Run from services/api so the
provider key comes from TraceroAI's settings; it is never printed.
This trial used: python make_questions.py corpus questions.json 4

    python make_questions.py <corpus dir> <out.json> [per_page]
"""

import json
import re
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, ".")
from app.core.config import get_settings  # noqa: E402

PROMPT = """You write evaluation questions for a retrieval system over technical documentation.
From the page below, write {n} question/answer pairs that a developer might ask and that this page answers.
Rules:
- Each answer must be fully supported by the page. Prefer specific facts (names, defaults, behaviours).
- Each pair includes "quote": a verbatim sentence or phrase from the page (max 30 words) that supports the answer. Copy it exactly.
- Questions must make sense without seeing the page (no "this page", "the example above").
Return JSON: {{"pairs": [{{"question": "...", "answer": "...", "quote": "..."}}]}}

PAGE ({name}):
{text}"""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> None:
    corpus, out = Path(sys.argv[1]), Path(sys.argv[2])
    per_page = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.judge_base_url or None)
    model = settings.judge_model
    kept, dropped, usage = [], 0, {"prompt": 0, "completion": 0}
    for page in sorted(corpus.glob("*.md")):
        text = page.read_text(encoding="utf-8")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT.format(n=per_page, name=page.name, text=text)}],
            response_format={"type": "json_object"},
        )
        usage["prompt"] += response.usage.prompt_tokens if response.usage else 0
        usage["completion"] += response.usage.completion_tokens if response.usage else 0
        pairs = json.loads(response.choices[0].message.content or "{}").get("pairs", [])
        for pair in pairs:
            if pair.get("quote") and norm(pair["quote"]) in norm(text):
                kept.append({"page": page.name, **pair})
            else:
                dropped += 1
    out.write_text(json.dumps(kept, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"model={model} kept={len(kept)} dropped={dropped} tokens={usage}")


if __name__ == "__main__":
    main()
