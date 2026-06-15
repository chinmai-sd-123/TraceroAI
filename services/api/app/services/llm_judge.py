from typing import Protocol

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import get_settings


class JudgedClaim(BaseModel):
    claim: str
    supported: bool
    reason: str


class ClaimGroundednessVerdict(BaseModel):
    claims: list[JudgedClaim]


class LLMJudge(Protocol):
    def judge_claim_groundedness(
        self, answer: str, context: str
    ) -> ClaimGroundednessVerdict: ...


SYSTEM_PROMPT = (
    "You are a strict groundedness judge for a RAG system. "
    "You are given an ANSWER and the CONTEXT that was retrieved to support it. "
    "Break the answer into distinct factual claims. For each claim, decide whether "
    "the context directly supports it. Mark a claim supported ONLY if the context "
    "entails it; do not rely on outside knowledge. Give a one-sentence reason per claim."
)


class OpenAIJudge:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.judge_model

    def judge_claim_groundedness(
        self, answer: str, context: str
    ) -> ClaimGroundednessVerdict:
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"CONTEXT:\n{context}\n\nANSWER:\n{answer}",
                },
            ],
            response_format=ClaimGroundednessVerdict,
        )

        verdict = completion.choices[0].message.parsed
        if verdict is None:
            raise ValueError("Judge returned no parsed verdict.")

        return verdict
