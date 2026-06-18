"""Correctness grading endpoint for the eval harness.

The SDK eval harness runs a client's RAG pipeline locally, then calls this to grade
each answer against its expected answer — so grading uses the SAME server-side LLM
judge as everything else (single source of truth). Keeps the grading judge off the
client; the client only orchestrates.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.llm_judge import OpenAIJudge

router = APIRouter(prefix="/v1/eval", tags=["eval"])


class GradeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    expected: str = Field(..., min_length=1)
    actual: str = Field(..., min_length=1)


class GradeResponse(BaseModel):
    correct: bool
    reason: str


@router.post("/grade", response_model=GradeResponse)
def grade_answer(payload: GradeRequest) -> GradeResponse:
    settings = get_settings()
    if not (settings.deep_eval_enabled and settings.openai_api_key):
        # No judge configured — can't grade. 503 so the caller can mark the case
        # ungradeable rather than silently scoring it wrong.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Grading is unavailable: no LLM judge is configured.",
        )
    try:
        verdict = OpenAIJudge().judge_answer_correctness(
            payload.question, payload.expected, payload.actual
        )
    except Exception as exc:  # provider error / rate limit
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Grading failed: {type(exc).__name__}",
        ) from exc

    return GradeResponse(correct=verdict.correct, reason=verdict.reason)
