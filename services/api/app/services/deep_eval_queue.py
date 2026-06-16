from uuid import UUID
import redis

from app.core.config import get_settings

QUEUE_NAME = "traceroai:deep_eval"

def _client() -> redis.Redis | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    return redis.Redis.from_url(
        settings.redis_url, decode_responses=True , socket_connect_timeout= 2
    )

def enqueue_deep_eval_request(trace_id : UUID) -> bool:
    """push a trace_id to the deep_eval queue.
    returns True if the request was successfully enqueued, False otherwise.also caller ahould fallback to the default behavior if this returns False.
    """
    client = _client()
    if client is None:
        return False
    try:
        client.lpush(QUEUE_NAME, str(trace_id))
        return True
    except redis.exceptions.RedisError:
        return False

def queue_stats() -> dict:
    """Return deep-eval queue health: depth + whether Redis is reachable.

    Degrades gracefully — if Redis is unconfigured or unreachable, reports
    redis_connected=False (the app falls back to BackgroundTasks).
    """
    client = _client()
    if client is None:
        return {"redis_connected": False, "queued": 0}
    try:
        return {"redis_connected": True, "queued": client.llen(QUEUE_NAME)}
    except redis.exceptions.RedisError:
        return {"redis_connected": False, "queued": 0}
