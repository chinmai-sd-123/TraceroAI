from typing import Any
from uuid import UUID

import httpx

from traceroai.trace import TraceContext


class TraceroClient:
    def __init__(self, base_url: str, api_key: str| None = None, timeout_seconds: float = 10.0,)-> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

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
        """Decorator for a RAG function that returns (answer, chunks).

        The first positional arg of the wrapped function is treated as the query.

            @client.traced(model="gpt-4o-mini")
            def answer(query: str) -> tuple[str, list[dict]]:
                chunks = retrieve(query)
                return generate(query, chunks), chunks
        """

        def decorator(func):
            def wrapper(query: str, *args: Any, **kwargs: Any):
                with self.trace(query) as t:
                    answer, chunks = func(query, *args, **kwargs)
                    t.log_retrieval(chunks, strategy=strategy)
                    t.log_generation(answer, model=model)
                    return answer

            return wrapper

        return decorator

    def log_trace(self , *,query:dict[str, Any],
                  retrieval: dict[str, Any],
                  generation: dict[str, Any],
                  prompt: dict[str, Any] | None = None,
                  latency: dict[str, Any] | None = None,
                  project: dict[str, Any]| None = None,
                  metadata: dict[str, Any] | None = None,
            )-> UUID:
                # Note: evaluations and diagnosis are computed server-side (the
                # server is the source of truth), so they are intentionally not
                # accepted here — sending them would be silently ignored.
                payload = {
                "query": query,
                "retrieval": retrieval,
                "generation": generation,
                "prompt": prompt or {},
                "latency": latency or {},
                "project": project or {},
                "metadata": metadata or {},
                }

                headers= {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                
                response = httpx.post(f"{self.base_url}/v1/traces", json=payload, headers=headers, timeout=self.timeout_seconds,)

                response.raise_for_status()

                data = response.json()
                return UUID(data["trace_id"])

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
        timeout_seconds: float | None = None,
    ) -> tuple[UUID, dict[str, Any] | None]:
        """Send a trace and run the deep (LLM-judge) eval SYNCHRONOUSLY, returning the
        judge-corrected diagnosis in the response. Used by the recovery agent, which
        must route on a judge-quality diagnosis immediately rather than poll the async
        deep-eval queue.

        Returns (trace_id, diagnosis) where diagnosis is {"label", "reason"} or None if
        the server didn't produce one (e.g. the judge was unavailable — the caller then
        falls back to fetching the quick diagnosis).

        Uses a longer timeout by default because the judge makes several LLM calls.
        """
        payload = {
            "query": query,
            "retrieval": retrieval,
            "generation": generation,
            "prompt": prompt or {},
            "latency": latency or {},
            "project": project or {},
            "metadata": metadata or {},
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(
            f"{self.base_url}/v1/traces",
            params={"sync_deep_eval": "true"},
            json=payload,
            headers=headers,
            timeout=timeout_seconds or max(self.timeout_seconds * 6, 60.0),
        )
        response.raise_for_status()
        data = response.json()
        return UUID(data["trace_id"]), data.get("diagnosis")

    def get_trace(self, trace_id: UUID | str) -> dict[str, Any]:
        """Fetch a stored trace by its ID. Returns the full trace object, including evaluations and diagnosis.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.get(f"{self.base_url}/v1/traces/{trace_id}", headers=headers, timeout=self.timeout_seconds,)
        response.raise_for_status()
        return response.json()