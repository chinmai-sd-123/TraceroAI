import redis

from app.core.config import get_settings


def _client() -> redis.Redis | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    return redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=2
    )


def check_rate_limit(bucket: str, identity: str, *, limit: int, window_seconds: int) -> bool:
    """Fixed-window rate limit. Returns True if the call is ALLOWED.

    Fails open: if Redis is unconfigured or unreachable, the call is allowed —
    a limiter protecting a public demo must never be the thing that breaks it.
    """
    client = _client()
    if client is None:
        return True
    key = f"traceroai:ratelimit:{bucket}:{identity}"
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_seconds)  # start the window on first hit
        return count <= limit
    except redis.exceptions.RedisError:
        return True
