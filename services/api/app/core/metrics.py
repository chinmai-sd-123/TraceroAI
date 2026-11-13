"""Prometheus metrics for the API and the worker.

Request metrics are labelled with the route template (/v1/traces/{trace_id}),
never the raw path, so ids don't create a new time series per request.
"""

from __future__ import annotations

import logging
import time

from prometheus_client import Counter, Histogram
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import REGISTRY, Collector
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter(
    "traceroai_http_requests_total",
    "HTTP requests handled, by route template and status code.",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "traceroai_http_request_duration_seconds",
    "Time to produce a response, by route template.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
TRACES_INGESTED = Counter(
    "traceroai_traces_ingested_total",
    "Traces received on POST /v1/traces: stored, or already stored (a resend).",
    ["outcome"],
)
DEEP_EVALUATIONS = Counter(
    "traceroai_deep_evaluations_total",
    "Finished background evaluations, by resulting judge status.",
    ["status"],
)


class MetricsMiddleware:
    """Count and time every HTTP request by route template and status."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = 500  # if the app raises before responding

        async def record_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, record_status)
        finally:
            # Starlette stores the matched route in the scope; unmatched paths
            # (404s, scanners) share one label.
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            method = scope["method"]
            HTTP_REQUESTS.labels(method, route, str(status)).inc()
            HTTP_DURATION.labels(method, route).observe(time.perf_counter() - started)


class QueueCollector(Collector):
    """Deep-eval queue depth, read from Redis when Prometheus scrapes."""

    def collect(self):
        from app.services.deep_eval_queue import queue_stats

        stats = queue_stats()
        connected = GaugeMetricFamily(
            "traceroai_queue_redis_connected", "1 if the deep-eval queue's Redis is reachable."
        )
        connected.add_metric([], 1 if stats["redis_connected"] else 0)
        yield connected
        depth = GaugeMetricFamily(
            "traceroai_queue_jobs", "Deep-eval jobs by state.", labels=["state"]
        )
        for state in ("queued", "pending", "dead_lettered"):
            depth.add_metric([state], stats[state])
        yield depth


_queue_collector_registered = False


def register_queue_collector() -> None:
    global _queue_collector_registered
    if not _queue_collector_registered:
        REGISTRY.register(QueueCollector())
        _queue_collector_registered = True
