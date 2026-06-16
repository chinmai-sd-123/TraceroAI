import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _no_real_llm_calls(monkeypatch):
    # Never hit the OpenAI network in tests, regardless of what's in .env.
    # Deep evaluation still RUNS (so stub-judge tests work) — it just can't build
    # a real judge, so route-triggered runs degrade to an `error` EvaluationResult.
    monkeypatch.setattr(get_settings(), "openai_api_key", None)
