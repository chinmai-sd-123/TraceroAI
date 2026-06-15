from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    database_url: str= "postgresql+psycopg://traceroai:traceroai@localhost:5432/traceroai"
    app_env: Literal["development", "testing", "staging", "production"] = "development"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TRACEROAI_", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    return Settings()   
