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
                  evaluation: dict[str, Any] | None = None,
                  diagnosis: dict[str, Any] | None = None,
                  project: dict[str, Any]| None = None,
                  metadata: dict[str, Any] | None = None,
            )-> UUID:
                payload = {
                "query": query,
                "retrieval": retrieval,
                "generation": generation,    
                "prompt": prompt or {},
                "latency": latency or {},
                "evaluation": evaluation or {},
                "diagnosis": diagnosis or {},
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
                
                