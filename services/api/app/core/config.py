from functools import lru_cache
from pathlib import Path
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
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix="TRACEROAI_", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()