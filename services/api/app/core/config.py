from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


# Anchor .env to the repo root so config loads regardless of the working
# directory the API is launched from (env_file="..." is otherwise CWD-relative).
ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://traceroai:traceroai@localhost:5432/traceroai"
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    openai_api_key: str | None = None
    judge_model: str = "gpt-4o-mini"
    deep_eval_enabled: bool = True
    redis_url: str | None = None
    # Multi-tenant lite: maps an API key -> project_id. JSON object string, e.g.
    # TRACEROAI_PROJECT_API_KEYS='{"key_acme":"acme","key_globex":"globex"}'.
    # An ingest request authenticated with a known key is stamped with that
    # project; unknown/absent keys fall back to the client-provided project.
    project_api_keys: dict[str, str] = Field(default_factory=dict)
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="TRACEROAI_", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()