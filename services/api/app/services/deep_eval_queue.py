"""Deep-eval job queue on a Redis Stream with a consumer group.

Why a stream instead of a list: a list pop deletes the job the moment a worker
takes it, so a crash mid-evaluation loses it. With a consumer group a job stays
pending until the worker acknowledges it (XACK). Jobs a dead worker left pending
are reclaimed by another worker (XAUTOCLAIM), and jobs that keep failing go to
a dead-letter stream instead of retrying forever. The worker side lives in
app/worker.py; this module is what the API needs: enqueue + stats.
"""

from uuid import UUID

import redis

from app.core.config import get_settings

STREAM = "traceroai:deep_eval:stream"
GROUP = "deep-eval-workers"
DEAD_LETTER_STREAM = "traceroai:deep_eval:dead"
# The pre-stream list queue. The worker drains it once at startup so jobs queued
# by an older API version aren't stranded.
LEGACY_LIST = "traceroai:deep_eval"
# Approximate cap on stream length so memory stays bounded on small managed Redis
# plans. Far above any realistic backlog.
STREAM_MAXLEN = 10_000


def _client() -> redis.Redis | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    return redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=2
    )


def enqueue_deep_eval_request(trace_id: UUID) -> bool:
    """Add a deep-eval job for trace_id.

    Returns False if Redis is unconfigured or unreachable — the caller then
    falls back to running the evaluation in-process.
    """
    client = _client()
    if client is None:
        return False
    try:
        client.xadd(STREAM, {"trace_id": str(trace_id)}, maxlen=STREAM_MAXLEN, approximate=True)
        return True
    except redis.exceptions.RedisError:
        return False


def queue_stats() -> dict:
    """Deep-eval queue health.

    - queued: jobs no worker has picked up yet
    - pending: jobs a worker picked up but hasn't finished (or that are
      waiting for a retry)
    - dead_lettered: jobs that exhausted their retries

    Degrades gracefully: unconfigured/unreachable Redis reports
    redis_connected=False (the app then falls back to BackgroundTasks).
    """
    empty = {"redis_connected": False, "queued": 0, "pending": 0, "dead_lettered": 0}
    client = _client()
    if client is None:
        return empty
    try:
        queued, pending = _group_backlog(client)
        return {
            "redis_connected": True,
            "queued": queued + client.llen(LEGACY_LIST),
            "pending": pending,
            "dead_lettered": client.xlen(DEAD_LETTER_STREAM),
        }
    except redis.exceptions.RedisError:
        return empty


def _group_backlog(client: redis.Redis) -> tuple[int, int]:
    """(undelivered, pending) for the worker group."""
    if not client.exists(STREAM):
        return 0, 0
    groups = {g["name"]: g for g in client.xinfo_groups(STREAM)}
    group = groups.get(GROUP)
    if group is None:
        # No worker has ever started: everything in the stream is undelivered.
        return client.xlen(STREAM), 0
    lag = group.get("lag")
    if lag is None:
        # Redis < 7 doesn't report lag; count entries after the group's cursor.
        lag = len(client.xrange(STREAM, min=f"({group['last-delivered-id']}", count=STREAM_MAXLEN))
    return int(lag), int(group["pending"])
