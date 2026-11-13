"""TraceroAI client.

Sending a trace never raises into your code and never waits on the network in
your thread: by default traces go onto a bounded in-memory queue and a
background thread delivers them, retrying temporary failures. Failures are
logged on the "traceroai" logger.

Short-lived processes (scripts, serverless handlers, tests) should call
client.flush() before exiting; an exit hook also flushes briefly.
"""

from __future__ import annotations

import atexit
import functools
import inspect
import logging
import os
import queue
import random
import threading
import time
from typing import Any
from uuid import UUID, uuid4

import httpx

from traceroai._version import __version__
from traceroai.trace import TraceContext

logger = logging.getLogger("traceroai")

# Server answers worth retrying: timeouts, rate limits, and server-side errors.
# Ingest is idempotent on trace_id, so resending a trace that did arrive is safe.
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
_MAX_BACKOFF_SECONDS = 10.0
_FAILURE_LOG_INTERVAL_SECONDS = 60.0


class TraceroError(Exception):
    """A trace could not be delivered (raised only with raise_on_error=True)."""


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


class TraceroClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        *,
        enabled: bool | None = None,
        background: bool = True,
        max_queue_size: int = 1000,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        raise_on_error: bool = False,
        flush_on_exit_seconds: float = 2.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """
        base_url / api_key: default to TRACEROAI_API_URL / TRACEROAI_API_KEY.
        enabled: False turns every send into a no-op (default: TRACEROAI_ENABLED,
            else True). Useful in tests and local runs.
        background: True (default) queues traces and sends them from a
            background thread. False sends in the calling thread, still without
            raising unless raise_on_error is set.
        max_queue_size: traces waiting to be sent; when full, new traces are
            dropped (and counted in dropped_traces) rather than using more memory.
        max_retries: extra attempts for timeouts, 429 and 5xx responses.
        raise_on_error: with background=False, raise TraceroError when a trace
            can't be delivered instead of logging it.
        transport: an httpx transport, for tests.
        """
        self.enabled = _env_flag("TRACEROAI_ENABLED", True) if enabled is None else enabled
        url = base_url or os.environ.get("TRACEROAI_API_URL")
        if not url:
            if self.enabled:
                raise ValueError(
                    "TraceroClient needs base_url (or the TRACEROAI_API_URL environment variable)."
                )
            url = "http://localhost"
        self.base_url = url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("TRACEROAI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.raise_on_error = raise_on_error

        self._http = httpx.Client(
            timeout=timeout_seconds,
            headers=self._headers(),
            transport=transport,
        )
        self._failures = _FailureLog()
        self._sender = (
            _BackgroundSender(self._deliver_quietly, max_queue_size, flush_on_exit_seconds)
            if background
            else None
        )

    # --- tracing helpers ---

    def trace(
        self,
        query: str,
        *,
        rewritten: str | None = None,
        project: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        """Open a trace context manager that auto-times and auto-sends.

        with client.trace("How long is a refund?") as t:
            t.log_retrieval(chunks)
            t.log_generation(answer, model="gpt-4o-mini")
        """
        return TraceContext(
            self, query, rewritten=rewritten, project=project, metadata=metadata
        )

    def traced(self, *, model: str, strategy: str = "vector"):
        """Decorator for a RAG function, sync or async, that returns (answer, chunks).

        The first positional arg of the wrapped function is treated as the query.

            @client.traced(model="gpt-4o-mini")
            def answer(query: str) -> tuple[str, list[dict]]:
                chunks = retrieve(query)
                return generate(query, chunks), chunks
        """

        def decorator(func):
            if inspect.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(query: str, *args: Any, **kwargs: Any):
                    with self.trace(query) as t:
                        answer, chunks = await func(query, *args, **kwargs)
                        t.log_retrieval(chunks, strategy=strategy)
                        t.log_generation(answer, model=model)
                        return answer

                return async_wrapper

            @functools.wraps(func)
            def wrapper(query: str, *args: Any, **kwargs: Any):
                with self.trace(query) as t:
                    answer, chunks = func(query, *args, **kwargs)
                    t.log_retrieval(chunks, strategy=strategy)
                    t.log_generation(answer, model=model)
                    return answer

            return wrapper

        return decorator

    # --- sending ---

    def log_trace(
        self,
        *,
        query: dict[str, Any],
        retrieval: dict[str, Any],
        generation: dict[str, Any],
        prompt: dict[str, Any] | None = None,
        latency: dict[str, Any] | None = None,
        project: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: UUID | str | None = None,
    ) -> UUID:
        """Send a trace and return its id.

        The id is generated here (or taken from trace_id), so it is known before
        the trace reaches the server and stays the same across retries. With the
        default background sending this returns immediately; the trace is
        delivered shortly after (call flush() to wait for it).

        Evaluations and diagnosis are computed server-side, so they aren't
        accepted here.
        """
        trace_id = UUID(str(trace_id)) if trace_id is not None else uuid4()
        if not self.enabled:
            return trace_id

        payload = {
            "trace_id": str(trace_id),
            "query": query,
            "retrieval": retrieval,
            "generation": generation,
            "prompt": prompt or {},
            "latency": latency or {},
            "project": project or {},
            "metadata": metadata or {},
        }
        if self._sender is not None:
            self._sender.enqueue(payload)
        elif self.raise_on_error:
            self._post_trace(payload)
        else:
            self._deliver_quietly(payload)
        return trace_id

    def log_trace_sync_eval(
        self,
        *,
        query: dict[str, Any],
        retrieval: dict[str, Any],
        generation: dict[str, Any],
        prompt: dict[str, Any] | None = None,
        latency: dict[str, Any] | None = None,
        project: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: UUID | str | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[UUID, dict[str, Any] | None]:
        """Send a trace and have the server run the LLM judge before answering.

        Returns (trace_id, diagnosis) where diagnosis is {"label", "reason"}.
        Unlike log_trace this waits for the server and raises on failure: it's
        for callers that need the verdict now (the recovery agent). Pass the
        same trace_id to a later log_trace to retry without a duplicate.
        """
        trace_id = UUID(str(trace_id)) if trace_id is not None else uuid4()
        payload = {
            "trace_id": str(trace_id),
            "query": query,
            "retrieval": retrieval,
            "generation": generation,
            "prompt": prompt or {},
            "latency": latency or {},
            "project": project or {},
            "metadata": metadata or {},
        }
        response = self._http.post(
            f"{self.base_url}/v1/traces",
            params={"sync_deep_eval": "true"},
            json=payload,
            # The server bounds the judge to about 45 seconds.
            timeout=timeout_seconds or max(self.timeout_seconds * 6, 60.0),
        )
        response.raise_for_status()
        data = response.json()
        return UUID(data["trace_id"]), data.get("diagnosis")

    def flush(self, timeout: float | None = None) -> bool:
        """Wait until queued traces have been sent (or given up on).

        Returns False if the timeout passed first. A no-op without background
        sending.
        """
        if self._sender is None:
            return True
        return self._sender.flush(self.timeout_seconds * 2 if timeout is None else timeout)

    @property
    def dropped_traces(self) -> int:
        """Traces discarded because the send queue was full."""
        return self._sender.dropped if self._sender is not None else 0

    # --- reading ---

    def get_trace(self, trace_id: UUID | str) -> dict[str, Any]:
        """Fetch a stored trace, with the server's evaluations and diagnosis.

        Waits for queued traces to be sent first, so a trace logged just before
        can be read back. Raises httpx.HTTPStatusError if it isn't found.
        """
        self.flush()
        response = self._http.get(f"{self.base_url}/v1/traces/{trace_id}")
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        """Send what's queued (briefly), then release the connection pool."""
        if self._sender is not None:
            self._sender.flush(self.timeout_seconds)
        self._http.close()

    # --- internals ---

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": f"traceroai-python/{__version__}"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post_trace(self, payload: dict[str, Any]) -> None:
        """POST one trace, retrying temporary failures. Raises TraceroError."""
        last_error = ""
        for attempt in range(self.max_retries + 1):
            if attempt:
                time.sleep(self._backoff(attempt))
            try:
                response = self._http.post(f"{self.base_url}/v1/traces", json=payload)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            if response.status_code < 400:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in _RETRYABLE_STATUSES:
                break  # the request itself is wrong (401, 413, 422, ...): retrying won't help
        raise TraceroError(f"trace {payload['trace_id']} was not sent ({last_error})")

    def _deliver_quietly(self, payload: dict[str, Any]) -> None:
        try:
            self._post_trace(payload)
        except Exception as exc:  # noqa: BLE001 - telemetry must never raise
            self._failures.record(exc)
        else:
            self._failures.recovered()

    def _backoff(self, attempt: int) -> float:
        delay = min(self.retry_backoff_seconds * 2 ** (attempt - 1), _MAX_BACKOFF_SECONDS)
        return delay * random.uniform(0.5, 1.0)


class _FailureLog:
    """Log send failures without flooding the log while the server is down."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_logged = 0.0
        self._suppressed = 0

    def record(self, error: Exception) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_logged and now - self._last_logged < _FAILURE_LOG_INTERVAL_SECONDS:
                self._suppressed += 1
                return
            suppressed, self._suppressed, self._last_logged = self._suppressed, 0, now
        more = f" ({suppressed} more failures since the last message)" if suppressed else ""
        logger.warning("TraceroAI: %s%s", error, more)

    def recovered(self) -> None:
        with self._lock:
            self._last_logged = 0.0
            self._suppressed = 0


_STOP = object()


class _BackgroundSender:
    """One daemon thread draining a bounded queue of traces."""

    def __init__(self, deliver, max_queue_size: int, flush_on_exit_seconds: float) -> None:
        self._deliver = deliver
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._pid = os.getpid()
        self.dropped = 0
        if flush_on_exit_seconds > 0:
            atexit.register(self.flush, flush_on_exit_seconds)

    def enqueue(self, payload: dict[str, Any]) -> None:
        self._ensure_running()
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            with self._lock:
                self.dropped += 1
                dropped = self.dropped
            if dropped == 1 or dropped % 100 == 0:
                logger.warning(
                    "TraceroAI: send queue is full; %d trace(s) dropped so far", dropped
                )

    def flush(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._queue.all_tasks_done.wait(remaining)
        return True

    def _ensure_running(self) -> None:
        with self._lock:
            # A forked child inherits the queue but not the thread: start a new one.
            if self._thread is not None and self._thread.is_alive() and self._pid == os.getpid():
                return
            if self._pid != os.getpid():
                self._queue = queue.Queue(maxsize=self._queue.maxsize)
                self._pid = os.getpid()
            self._thread = threading.Thread(
                target=self._run, name="traceroai-sender", daemon=True
            )
            self._thread.start()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                self._deliver(item)
            except Exception:  # noqa: BLE001 - keep the thread alive no matter what
                logger.exception("TraceroAI: unexpected error in the sender thread")
            finally:
                self._queue.task_done()
