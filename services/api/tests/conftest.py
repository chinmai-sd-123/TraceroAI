import os
from urllib.parse import urlsplit

import pytest

# Tests write traces, eval runs and feedback, so they must never run against the
# database in .env (which may be production). Point the app at a dedicated test
# database before any app module builds its engine. Environment variables take
# precedence over .env in pydantic-settings.
TEST_DATABASE_URL = os.environ.get(
    "TRACEROAI_TEST_DATABASE_URL",
    "postgresql+psycopg://traceroai:traceroai@localhost:5432/traceroai_test",
)
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}

if urlsplit(TEST_DATABASE_URL).hostname not in _LOCAL_HOSTS:
    pytest.exit(
        f"Refusing to run tests against non-local database host "
        f"{urlsplit(TEST_DATABASE_URL).hostname!r}. Set TRACEROAI_TEST_DATABASE_URL "
        "to a local or CI Postgres.",
        returncode=2,
    )
os.environ["TRACEROAI_DATABASE_URL"] = TEST_DATABASE_URL

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.init_db import init_db  # noqa: E402


def _ensure_database_exists(url: str) -> None:
    """Create the test database on first run (docker compose only creates
    `traceroai`). CI's Postgres service creates it up front."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": target.database},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> None:
    _ensure_database_exists(TEST_DATABASE_URL)
    init_db()


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    # Never touch real external services in tests, regardless of .env:
    # - no OpenAI network (deep eval degrades to an error result)
    # - no Redis (ingest falls back to BackgroundTasks)
    # - no LiteLLM price fetch (cost uses the built-in fallback table)
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "redis_url", None)
    # Unauthenticated writes allowed by default; auth tests opt in explicitly.
    monkeypatch.setattr(settings, "require_api_key", False)

    from app.services import cost
    monkeypatch.setattr(cost, "_litellm_cache", {})
