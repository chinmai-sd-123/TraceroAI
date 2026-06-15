from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    database_url: str= "postgresql+psycopg://traceroai:traceroai@localhost:5432/traceroai"
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    openai_api_key: str | None = None
    judge_model: str = "gpt-4o-mini"
    deep_eval_enabled: bool = True
    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRACEROAI_", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    return Settings()   
