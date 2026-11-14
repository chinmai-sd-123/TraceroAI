from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def engine_options(settings: Settings) -> dict[str, Any]:
    return {
        "pool_pre_ping": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        # Fail a request after this long waiting for a free connection rather than
        # queueing it behind a stalled pool for the 30-second default.
        "pool_timeout": settings.db_pool_timeout_seconds,
        # Without it, a database host that drops packets (rather than refusing)
        # holds every request, readiness checks included, for the operating
        # system's TCP timeout: 20 seconds to minutes.
        "connect_args": {"connect_timeout": settings.db_connect_timeout_seconds},
    }


settings = get_settings()
engine = create_engine(settings.database_url, **engine_options(settings))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
