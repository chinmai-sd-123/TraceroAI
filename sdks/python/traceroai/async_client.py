"""TraceroAI client for asyncio code.

The same guarantees as TraceroClient, without a thread: log_trace returns at
once and delivers the trace as a task on the running event loop, retrying
temporary failures; nothing raises into your code, and failures are logged on
the "traceroai" logger. Calls that need the server's answer are coroutines.

    client = AsyncTraceroClient(base_url="http://localhost:8000")

    async def answer(question: str) -> str:
        with client.trace(question) as t:          # `async with` works too
            chunks = await retrieve(question)
            t.log_retrieval(chunks)
            reply = await generate(question, chunks)
            t.log_generation(reply, model="gpt-4o-mini")
        return reply

    await client.aclose()   # sends what's pending, then closes the connection pool
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from typing import Any
from uuid import UUID, uuid4

import httpx

from traceroai.client import (
    _RETRYABLE_STATUSES,
    TraceroError,
    _backoff_delay,
    _env_flag,
    _FailureLog,
    _trace_payload,
    _user_agent_headers,
)
from traceroai.redaction import Redaction, RedactionError, Redactor
from traceroai.trace import TraceContext

logger = logging.getLogger("traceroai")


class AsyncTraceroClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        *,
        enabled: bool | None = None,
        max_pending: int = 1000,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
        redact: Redactor | None = None,
    ) -> None:
        """
        base_url / api_key: default to TRACEROAI_API_URL / TRACEROAI_API_KEY.
        enabled: False turns every send into a no-op (default: TRACEROAI_ENABLED,
            else True).
        max_pending: traces being delivered at once; beyond that new traces are
            dropped (and counted in dropped_traces) rather than piling up.
        max_retries: extra attempts for timeouts, 429 and 5xx responses.
        transport: an httpx async transport, for tests.
        redact: a function given a copy of each trace that returns the trace to
            send, or None to drop it (see traceroai.redaction). If it raises, the
            trace is dropped, never sent unredacted.
        """
        self.enabled = _env_flag("TRACEROAI_ENABLED", True) if enabled is None else enabled
        url = base_url or os.environ.get("TRACEROAI_API_URL")
        if not url:
            if self.enabled:
                raise ValueError(
                    "AsyncTraceroClient needs base_url (or the TRACEROAI_API_URL environment variable)."
                )
            url = "http://localhost"
        self.base_url = url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("TRACEROAI_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.max_pending = max_pending
        self.max_retries = max_retries
        self._redaction = Redaction(redact) if redact is not None else None
        self.retry_backoff_seconds = retry_backoff_seconds
        self.dropped_traces = 0

        self._http = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers=_user_agent_headers(self.api_key),
            transport=transport,
        )
        self._failures = _FailureLog()
        # Strong references, so a delivery task isn't garbage-collected mid-flight.
        self._pending: set[asyncio.Task[None]] = set()

    @property
    def redaction_failures(self) -> int:
        """Traces dropped because the redact function failed."""
        return self._redaction.failures if self._redaction is not None else 0

    async def __aenter__(self) -> AsyncTraceroClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # --- tracing helpers ---

    def trace(
        self,
        query: str,
        *,
        rewritten: str | None = None,
        project: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        """A context manager (`with` or `async with`) that times the block and sends the trace."""
        return TraceContext(self, query, rewritten=rewritten, project=project, metadata=metadata)

    def traced(self, *, model: str, strategy: str = "vector"):
        """Decorator for an async RAG function that returns (answer, chunks).

        The first positional argument of the wrapped function is the query.
        """

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(query: str, *args: Any, **kwargs: Any):
                with self.trace(query) as t:
                    answer, chunks = await func(query, *args, **kwargs)
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
        status: str | None = None,
    ) -> UUID:
        """Send a trace and return its id, without waiting for the network.

        Call it from code running on an event loop. The trace is delivered by a
        task on that loop; await flush() to wait for it.
        """
        trace_id = UUID(str(trace_id)) if trace_id is not None else uuid4()
        if not self.enabled:
            return trace_id
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("TraceroAI: AsyncTraceroClient.log_trace needs a running event loop; trace %s dropped", trace_id)
            return trace_id
        if len(self._pending) >= self.max_pending:
            self.dropped_traces += 1
            if self.dropped_traces == 1 or self.dropped_traces % 100 == 0:
                logger.warning("TraceroAI: too many traces in flight; %d dropped so far", self.dropped_traces)
            return trace_id

        payload = _trace_payload(
            trace_id,
            query=query,
            retrieval=retrieval,
            generation=generation,
            prompt=prompt,
            latency=latency,
            project=project,
            metadata=metadata,
            status=status,
        )
        if self._redaction is not None:
            redacted = self._redaction.apply_quietly(payload)
            if redacted is None:
                return trace_id
            payload = redacted
        task = loop.create_task(self._deliver_quietly(payload), name=f"traceroai-send-{trace_id}")
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        return trace_id

    async def log_trace_sync_eval(
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
        """Send a trace and wait for the LLM judge's verdict. Raises on failure."""
        trace_id = UUID(str(trace_id)) if trace_id is not None else uuid4()
        payload = _trace_payload(
            trace_id,
            query=query,
            retrieval=retrieval,
            generation=generation,
            prompt=prompt,
            latency=latency,
            project=project,
            metadata=metadata,
        )
        if self._redaction is not None:
            try:
                redacted = self._redaction.apply(payload)
            except RedactionError as exc:
                raise TraceroError(f"trace {trace_id} was not sent: {exc}") from exc
            if redacted is None:
                raise TraceroError(f"trace {trace_id} was dropped by redact, so it can't be judged")
            payload = redacted
        response = await self._http.post(
            f"{self.base_url}/v1/traces",
            params={"sync_deep_eval": "true"},
            json=payload,
            timeout=timeout_seconds or max(self.timeout_seconds * 6, 60.0),
        )
        response.raise_for_status()
        data = response.json()
        return UUID(data["trace_id"]), data.get("diagnosis")

    async def flush(self, timeout: float | None = None) -> bool:
        """Wait until traces in flight are sent (or given up on). False if the timeout passed first."""
        if not self._pending:
            return True
        _, still_pending = await asyncio.wait(
            set(self._pending), timeout=self.timeout_seconds * 2 if timeout is None else timeout
        )
        return not still_pending

    # --- reading ---

    async def get_trace(self, trace_id: UUID | str) -> dict[str, Any]:
        """Fetch a stored trace with its evaluations and diagnosis (after sending pending traces)."""
        await self.flush()
        response = await self._http.get(f"{self.base_url}/v1/traces/{trace_id}")
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        """Send what's pending (briefly), then release the connection pool."""
        await self.flush(self.timeout_seconds)
        await self._http.aclose()

    # --- internals ---

    async def _post_trace(self, payload: dict[str, Any]) -> None:
        last_error = ""
        for attempt in range(self.max_retries + 1):
            if attempt:
                await asyncio.sleep(_backoff_delay(self.retry_backoff_seconds, attempt))
            try:
                response = await self._http.post(f"{self.base_url}/v1/traces", json=payload)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            if response.status_code < 400:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code not in _RETRYABLE_STATUSES:
                break  # the request itself is wrong (401, 413, 422, ...): retrying won't help
        raise TraceroError(f"trace {payload['trace_id']} was not sent ({last_error})")

    async def _deliver_quietly(self, payload: dict[str, Any]) -> None:
        try:
            await self._post_trace(payload)
        except Exception as exc:  # noqa: BLE001 - telemetry must never raise
            self._failures.record(exc)
        else:
            self._failures.recovered()
