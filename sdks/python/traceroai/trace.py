"""Ergonomic tracing: a context manager that builds and sends a trace for you.

Instead of hand-assembling the log_trace(...) payload, wrap the RAG work:

    with client.trace(query="How long is a refund?") as t:
        t.log_retrieval(chunks, strategy="hybrid", config={"final_top_k": 3})
        t.log_prompt(prompt_text, version="grounded_v1")
        t.log_generation(answer, model="gpt-4o-mini")

The context manager times the block automatically, fills latency.total_ms, marks
the trace unanswered if an exception escapes, and sends it on exit.
"""

from __future__ import annotations

import time
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
    ) -> None:
        self._generation = {
            "answer": answer,
            "answered": True,
            "model": model,
            "provider": provider,
            "temperature": temperature,
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

        self.trace_id = self._client.log_trace(
            query=self._query,
            retrieval=self._retrieval,
            generation=self._generation,
            prompt=self._prompt,
            latency={"total_ms": total_ms},
            project=self._project,
            metadata=self._metadata,
        )
        return False  # never suppress exceptions
