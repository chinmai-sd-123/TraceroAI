"""Fixed-window rate limits for the endpoints anyone can call.

Counts live in Redis when it's configured, so every API process shares them.
Without Redis, or while it's unreachable, each process counts on its own: the
limit still holds per process instead of switching off. (It used to fail open,
which left the paid-for playground unlimited exactly when Redis was down.)
"""

from __future__ import annotations

import ipaddress
import threading
import time

import redis
from fastapi import Request

from app.core.config import get_settings


def client_ip(request: Request) -> str:
    """The caller's address, for per-client limits.

    X-Forwarded-For is only trusted for the hops we know are ours: with
    TRACEROAI_TRUSTED_PROXY_COUNT=N, the Nth entry from the right is the address
    our outermost proxy saw. Entries further left are whatever the client sent,
    so trusting them (as this used to) let any caller pick a fresh identity per
    request. With 0 (the default, no proxy) the socket peer is used.
    """
    peer = request.client.host if request.client else "unknown"
    hops = get_settings().trusted_proxy_count
    if hops <= 0:
        return peer
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",")]
    forwarded = [part for part in forwarded if part]
    if len(forwarded) < hops:
        return peer
    candidate = forwarded[-hops]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


def _redis() -> redis.Redis | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    return redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=2
    )


class _LocalWindows:
    """Per-process fixed windows, used when Redis isn't available."""

    _MAX_KEYS = 50_000  # bound memory if many distinct callers show up

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            started, count = self._windows.get(key, (now, 0))
            if now - started >= window_seconds:
                started, count = now, 0
            count += 1
            self._windows[key] = (started, count)
            if len(self._windows) > self._MAX_KEYS:
                self._evict_expired(now, window_seconds)
            return count <= limit

    def _evict_expired(self, now: float, window_seconds: int) -> None:
        expired = [k for k, (started, _) in self._windows.items() if now - started >= window_seconds]
        for key in expired:
            del self._windows[key]
        if len(self._windows) > self._MAX_KEYS:  # still full: drop the oldest half
            oldest = sorted(self._windows, key=lambda k: self._windows[k][0])
            for key in oldest[: len(oldest) // 2]:
                del self._windows[key]

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()


_local = _LocalWindows()


def check_rate_limit(bucket: str, identity: str, *, limit: int, window_seconds: int) -> bool:
    """Count one call; True if it's within the limit."""
    key = f"traceroai:ratelimit:{bucket}:{identity}"
    client = _redis()
    if client is not None:
        try:
            count = client.incr(key)
            if count == 1:
                client.expire(key, window_seconds)  # start the window on first hit
            return count <= limit
        except redis.exceptions.RedisError:
            pass  # fall through to the per-process count
    return _local.hit(key, limit=limit, window_seconds=window_seconds)
