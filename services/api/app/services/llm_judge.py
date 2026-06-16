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

class RelevanceVerdict(BaseModel):
    relevant: bool
    reason: str


class LLMJudge(Protocol):
    def judge_claim_groundedness(
        self, answer: str, context: str
    ) -> ClaimGroundednessVerdict: ...

    def judge_context_relevance(self, answer: str, context: str) -> RelevanceVerdict: ...
    def judge_answer_relevance(self, answer: str, context: str) -> RelevanceVerdict: ...


SYSTEM_PROMPT = (
    "You are a strict groundedness judge for a RAG system. "
    "You are given an ANSWER and the CONTEXT that was retrieved to support it. "
    "Break the answer into distinct factual claims. For each claim, decide whether "
    "the context directly supports it. Mark a claim supported ONLY if the context "
    "entails it; do not rely on outside knowledge. Give a one-sentence reason per claim."
)

CONTEXT_RELEVANCE_PROMPT = (
    "You judge retrieval quality for a RAG system. Given a QUERY and the "
    "retrieved CONTEXT, decide whether the context contains information that "
    "helps answer the query. Set relevant=true only if it does. Reason in one "
    "sentence. Judge meaning, not word overlap."

)

ANSWER_RELEVANCE_PROMPT = (
    "You judge whether an ANSWER addresses a QUERY for a RAG system. Set "
    "relevant=true only if the answer directly addresses what the query asks. "
    "Reason in one sentence. Judge meaning, not word overlap."
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
    
    def _judge_relevance(self, system_prompt: str, user_content: str) -> RelevanceVerdict:
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format=RelevanceVerdict,
        )
        verdict = completion.choices[0].message.parsed
        if verdict is None:
            raise ValueError("Judge returned no parsed verdict.")
        return verdict

    def judge_context_relevance(self, query: str, context: str) -> RelevanceVerdict:
        return self._judge_relevance(
            CONTEXT_RELEVANCE_PROMPT, f"QUERY:\n{query}\n\nCONTEXT:\n{context}"
        )

    def judge_answer_relevance(self, query: str, answer: str) -> RelevanceVerdict:
        return self._judge_relevance(
            ANSWER_RELEVANCE_PROMPT, f"QUERY:\n{query}\n\nANSWER:\n{answer}"
        )

