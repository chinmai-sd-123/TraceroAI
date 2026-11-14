"""Liveness, readiness and Prometheus metrics.

- /health        the process is up (for restarts).
- /health/ready  the API can serve traffic: the database answers, and Redis if
                 one is configured. 503 otherwise (for load balancers).
- /metrics       Prometheus text format.

Failures are reported by component name only: exception messages can carry
hostnames or credentials, and these endpoints are reachable without a key.
"""

import logging

import redis
import redis.exceptions as redis_exceptions
from fastapi import APIRouter, Depends, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.tenancy import Caller, api_key_required, caller
from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def _database_ok() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("Readiness: database check failed", exc_info=True)
        return False


def _redis_status() -> str:
    url = get_settings().redis_url
    if not url:
        return "not_configured"
    try:
        redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2).ping()
        return "ok"
    except redis_exceptions.RedisError:
        logger.warning("Readiness: Redis check failed", exc_info=True)
        return "unavailable"


@router.get("/health/ready")
def readiness(response: Response) -> dict:
    checks = {
        "database": "ok" if _database_ok() else "unavailable",
        "redis": _redis_status(),
    }
    ready = checks["database"] == "ok" and checks["redis"] != "unavailable"
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if ready else "unavailable", "checks": checks}


@router.get("/health/db")
def health_check_db(response: Response) -> dict[str, str]:
    """Kept for existing monitors; /health/ready covers it."""
    if _database_ok():
        return {"status": "ok"}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "unavailable"}


def _metrics_access(who: Caller = Depends(caller)) -> None:
    # Counts by route are low-sensitivity, but where keys are required only an
    # admin key (a Prometheus scraper's) may read them.
    if api_key_required() and not who.is_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="An admin API key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/metrics", include_in_schema=False, dependencies=[Depends(_metrics_access)])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
