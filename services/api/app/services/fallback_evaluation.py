"""In-process deep evaluation, for when Redis isn't configured or is down.

A few dedicated threads, separate from the pool that serves API requests:
before this, each fallback evaluation ran as a FastAPI background task on that
shared pool and held a request thread for as long as the LLM calls took.

Jobs here live in memory only and are lost if the process restarts. Configure
Redis and run the worker (`python -m app.worker`) for anything beyond local use.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from uuid import UUID

from app.core.config import get_settings
from app.services.deep_evaluation import run_deep_evaluation

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(
    max_workers=get_settings().fallback_eval_workers,
    thread_name_prefix="deep-eval-fallback",
)


def submit_fallback_evaluation(trace_id: UUID) -> Future:
    """Queue the trace's deep evaluation on the fallback threads and return."""
    return _executor.submit(_run, trace_id)


def _run(trace_id: UUID) -> None:
    try:
        run_deep_evaluation(trace_id)
    except Exception:
        logger.exception("In-process deep evaluation failed for %s", trace_id)
