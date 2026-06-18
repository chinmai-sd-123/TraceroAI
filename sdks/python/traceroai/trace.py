"""Ergonomic tracing: a context manager that builds and sends a trace for you.

Instead of hand-assembling the log_trace(...) payload, wrap the RAG work:

    with client.trace(query="How long is a refund?") as t:
        t.log_retrieval(chunks, strategy="hybrid", config={"final_top_k": 3})
        t.log_prompt(prompt_text, version="grounded_v1")
        t.log_generation(answer, model="gpt-4o-mini")

The context manager times the block automatically, fills latency.total_ms, marks
the trace unanswered if an exception escapes, and sends it on exit. Sending is
best-effort: a logging/network failure never breaks the caller's code or masks
the caller's own exception (it warns and leaves trace_id as None).
"""

from __future__ import annotations

import time
import warnings
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from traceroai.client import TraceroClient


class TraceContext:
    def __init__(
        self,
        client: "TraceroClient",
        query: str,
        *,
        rewritten: str | None = None,
        project: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._query: dict[str, Any] = {"original": query}
        if rewritten is not None and rewritten != query:
            self._query.update({"rewritten": rewritten, "rewrite_changed": True})

        self._retrieval: dict[str, Any] = {"chunks": []}
        self._prompt: dict[str, Any] | None = None
        self._generation: dict[str, Any] = {"answer": "", "answered": False}
        self._project = project
        self._metadata = metadata

        self._start: float = 0.0
        self.trace_id: UUID | None = None

    # --- piece loggers (call these inside the `with` block) ---

    def log_retrieval(
        self,
        chunks: list[dict[str, Any]],
        *,
        strategy: str = "vector",
        config: dict[str, Any] | None = None,
    ) -> None:
        self._retrieval = {"strategy": strategy, "chunks": chunks}
        if config is not None:
            self._retrieval["config"] = config

    def log_prompt(
        self, content: str, *, version: str | None = None, template_name: str | None = None
    ) -> None:
        self._prompt = {"content": content, "version": version, "template_name": template_name}

    def log_generation(
        self,
        answer: str,
        *,
        model: str,
        provider: str | None = None,
        temperature: float | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        self._generation = {
            "answer": answer,
            "answered": True,
            "model": model,
            "provider": provider,
            "temperature": temperature,
        }
        # Token counts feed server-side cost tracking. Cost itself is computed by
        # the server from its price table.
        if prompt_tokens is not None or completion_tokens is not None:
            self._generation["usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }

    # --- context manager protocol ---

    def __enter__(self) -> "TraceContext":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        total_ms = int((time.perf_counter() - self._start) * 1000)

        # A generation is only "answered" if one was logged and nothing blew up.
        if exc_type is not None:
            self._generation["answered"] = False

        # The schema requires a model; default it so a half-finished trace still sends.
        self._generation.setdefault("model", "unknown")

        # The schema requires a non-empty answer. If generation failed/was skipped,
        # record a placeholder (with the error, if any) so the FAILURE is still
        # captured as a trace instead of being dropped.
        if not self._generation.get("answer"):
            self._generation["answer"] = (
                f"[generation failed: {exc}]" if exc is not None else "[no answer generated]"
            )

        # Telemetry is best-effort: a failure to send a trace must NEVER break the
        # caller's app, nor mask the caller's own exception. On send failure we
        # warn and leave trace_id as None.
        try:
            self.trace_id = self._client.log_trace(
                query=self._query,
                retrieval=self._retrieval,
                generation=self._generation,
                prompt=self._prompt,
                latency={"total_ms": total_ms},
                project=self._project,
                metadata=self._metadata,
            )
        except Exception as send_error:  # noqa: BLE001 - intentionally broad
            warnings.warn(
                f"TraceroAI: failed to send trace: {send_error}", stacklevel=2
            )

        return False  # never suppress the caller's exception
