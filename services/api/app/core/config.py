from functools import lru_cache
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


# Anchor .env to the repo root so config loads regardless of the working
# directory the API is launched from (env_file="..." is otherwise CWD-relative).
# In the Docker image the app sits at /app/app/core/config.py, which has no repo
# root above it; there, configuration comes from the environment only.
_PARENTS = Path(__file__).resolve().parents
ENV_FILE = _PARENTS[4] / ".env" if len(_PARENTS) > 4 else None


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://traceroai:traceroai@localhost:5432/traceroai"
    app_env: Literal["development", "testing", "staging", "production"] = "development"
    log_level: str = "INFO"
    openai_api_key: str | None = None
    judge_model: str = "gpt-4o-mini"
    embedding_model: str = "gemini-embedding-001"

    # Optional: point the judge at any OpenAI-compatible endpoint (e.g. Gemini's
    # https://generativelanguage.googleapis.com/v1beta/openai/ ). When set,
    # openai_api_key holds that provider's key and judge_model its model name.
    judge_base_url: str | None = None
    deep_eval_enabled: bool = True
    redis_url: str | None = None
    # Multi-tenant lite: maps an API key -> project_id. JSON object string, e.g.
    # TRACEROAI_PROJECT_API_KEYS='{"key_acme":"acme","key_globex":"globex"}'.
    # An ingest request authenticated with a known key is stamped with that
    # project; unknown/absent keys fall back to the client-provided project.
    project_api_keys: dict[str, str] = Field(default_factory=dict)
    # Keys that may read every project and write to any (the dashboard server
    # uses one). JSON list: TRACEROAI_ADMIN_API_KEYS='["<long random key>"]'.
    admin_api_keys: list[str] = Field(default_factory=list)
    # Projects that callers without a key may read when keys are required, e.g.
    # a public demo: TRACEROAI_PUBLIC_READ_PROJECTS='["playground"]'.
    public_read_projects: list[str] = Field(default_factory=list)
    # Whether requests must carry a valid key. Unset = required in
    # staging/production, optional in development/testing (see
    # core/tenancy.api_key_required). When required, writes without a key get a
    # 401 and reads without a key see only public_read_projects.
    require_api_key: bool | None = None
    # Extra browser origins allowed by CORS (the deployed frontend URL).
    # JSON list, e.g. TRACEROAI_CORS_ORIGINS='["https://traceroai.vercel.app"]'.
    cors_origins: list[str] = Field(default_factory=list)
    # Largest request body the API accepts, in bytes (413 above it). One trace
    # with dozens of full-text chunks fits comfortably in the default.
    max_request_bytes: int = Field(default=1_000_000, gt=0)
    # Database connection pool per process. Requests hold a connection only for
    # their queries (evaluation never holds one across LLM calls), so the
    # defaults serve far more concurrent requests than their sum.
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    db_pool_timeout_seconds: float = Field(default=10.0, gt=0)
    # Threads for in-process deep evaluation when Redis is unavailable.
    fallback_eval_workers: int = Field(default=2, ge=1)
    # env_ignore_empty: an empty variable (TRACEROAI_X=, or an unset Compose
    # ${VAR:-}) means "use the default", rather than an empty string that the
    # JSON settings can't parse.
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_prefix="TRACEROAI_", extra="ignore", env_ignore_empty=True
    )

    @field_validator("judge_base_url", mode="before")
    @classmethod
    def _blank_base_url_is_none(cls, value: object) -> object:
        # An empty/whitespace base URL (e.g. TRACEROAI_JUDGE_BASE_URL= in .env to
        # switch from Gemini back to OpenAI) must become None — the OpenAI SDK
        # treats "" as a malformed URL and raises a connection error otherwise.
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()