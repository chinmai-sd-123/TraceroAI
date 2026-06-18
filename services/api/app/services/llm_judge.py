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


class CorrectnessVerdict(BaseModel):
    correct: bool
    reason: str


class LLMJudge(Protocol):
    def judge_claim_groundedness(
        self, answer: str, context: str
    ) -> ClaimGroundednessVerdict: ...

    def judge_context_relevance(self, answer: str, context: str) -> RelevanceVerdict: ...
    def judge_answer_relevance(self, answer: str, context: str) -> RelevanceVerdict: ...
    def judge_answer_correctness(
        self, question: str, expected: str, actual: str
    ) -> CorrectnessVerdict: ...


SYSTEM_PROMPT = (
    "You are a strict groundedness judge for a RAG system. You receive an ANSWER "
    "and the CONTEXT retrieved to support it.\n"
    "Decompose the answer into its distinct, atomic factual claims (ignore "
    "filler, citations like [1], hedging, and questions). For EACH claim decide "
    "if the CONTEXT directly supports it.\n"
    "Rules:\n"
    "- supported=true ONLY if the context explicitly states or unambiguously "
    "entails the claim. Paraphrase is fine; inference beyond the text is not.\n"
    "- Use ONLY the context. Never rely on outside or prior knowledge, even if "
    "the claim is true in reality.\n"
    "- If the answer is a refusal or contains no factual claims, return an empty "
    "claims list.\n"
    "Give a concise one-sentence reason per claim, quoting the supporting context "
    "when relevant."
)

CONTEXT_RELEVANCE_PROMPT = (
    "You judge RETRIEVAL quality for a RAG system. Given a QUERY and the retrieved "
    "CONTEXT, decide whether the context contains information that would help "
    "answer the query.\n"
    "- relevant=true if any part of the context is on-topic and useful for "
    "answering, even if incomplete.\n"
    "- relevant=false if the context is about a different topic or lacks anything "
    "usable.\n"
    "Judge meaning and intent, not keyword overlap. Reason in one sentence."
)

ANSWER_RELEVANCE_PROMPT = (
    "You judge whether an ANSWER actually addresses a QUERY for a RAG system.\n"
    "- relevant=true if the answer directly responds to what the query asks "
    "(a correct refusal when information is genuinely unavailable also counts as "
    "relevant).\n"
    "- relevant=false if it is off-topic, answers a different question, or evades "
    "the query.\n"
    "Judge intent, not keyword overlap. Reason in one sentence."
)

CORRECTNESS_PROMPT = (
    "You grade a RAG ANSWER against a reference EXPECTED answer for a QUESTION.\n"
    "Judge whether the actual answer is correct in substance:\n"
    "- correct=true if it conveys the same key fact(s) as expected and does not "
    "contradict them. Different wording, ordering, or extra correct detail is fine.\n"
    "- correct=false if it misses the key fact, states something contradictory, or "
    "is vague/evasive where a specific answer was expected.\n"
    "- If the expected answer is a refusal ('I don't know...'), then a refusal in "
    "the actual answer is correct, and a confident made-up answer is incorrect.\n"
    "Focus on factual substance, not style. Reason in one sentence."
)

class OpenAIJudge:
    """LLM judge over the OpenAI SDK. Works with OpenAI or any OpenAI-compatible
    endpoint (e.g. Gemini) by setting judge_base_url + the matching key/model."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.judge_base_url,  # None -> OpenAI default; set for Gemini
        )
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

    def judge_answer_correctness(
        self, question: str, expected: str, actual: str
    ) -> CorrectnessVerdict:
        completion = self._client.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": CORRECTNESS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"QUESTION:\n{question}\n\n"
                        f"EXPECTED:\n{expected}\n\n"
                        f"ACTUAL:\n{actual}"
                    ),
                },
            ],
            response_format=CorrectnessVerdict,
        )
        verdict = completion.choices[0].message.parsed
        if verdict is None:
            raise ValueError("Judge returned no parsed verdict.")
        return verdict

