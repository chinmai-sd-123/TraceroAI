import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    # Never touch real external services in tests, regardless of .env:
    # - no OpenAI network (deep eval degrades to an error result)
    # - no Redis (ingest falls back to BackgroundTasks)
    # - no LiteLLM price fetch (cost uses the built-in fallback table)
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "redis_url", None)

    from app.services import cost
    monkeypatch.setattr(cost, "_litellm_cache", {})
