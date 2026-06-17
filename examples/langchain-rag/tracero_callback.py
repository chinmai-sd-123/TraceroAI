"""A LangChain callback handler that auto-sends a TraceroAI trace.

This is the 'zero-touch' integration: attach the handler to a chain invocation
and it captures the retrieved documents and the generated answer from LangChain's
callback events, then sends a trace via the TraceroAI SDK's low-level log_trace.

    handler = TraceroAICallbackHandler(client, project_id="langchain-demo")
    chain.invoke(question, config={"callbacks": [handler]})

It is best-effort by design (mirroring the SDK): a logging failure never breaks
the chain.
"""

from __future__ import annotations

import time
import warnings
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.documents import Document

from rag_chain import docs_to_chunks


class TraceroAICallbackHandler(BaseCallbackHandler):
    def __init__(self, client, *, project_id: str = "langchain-demo", model: str = "gpt-4o-mini") -> None:
        self._client = client
        self._project_id = project_id
        self._model = model
        self._reset()

    def _reset(self) -> None:
        self._question: str | None = None
        self._chunks: list[dict] = []
        self._answer: str = ""
        self._start = time.perf_counter()
        self.trace_id: UUID | None = None

    # LangChain fires this when a chain starts; the inputs hold the question.
    def on_chain_start(self, serialized: dict, inputs: Any, **kwargs: Any) -> None:
        if self._question is None:
            if isinstance(inputs, dict):
                self._question = inputs.get("question") or inputs.get("input") or str(inputs)
            else:
                self._question = str(inputs)
            self._start = time.perf_counter()

    # Fired when the retriever returns documents.
    def on_retriever_end(self, documents: list[Document], **kwargs: Any) -> None:
        self._chunks = docs_to_chunks(documents)

    # Fired when the LLM finishes; pull the generated text out of the response.
    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            self._answer = response.generations[0][0].text
        except Exception:
            self._answer = ""

    # Fired when the whole chain finishes -> send the trace.
    def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
        # Only send on the OUTER chain end (when we have a question to attribute).
        if self._question is None:
            return

        answer = self._answer or (str(outputs) if outputs else "")
        total_ms = int((time.perf_counter() - self._start) * 1000)

        try:
            self.trace_id = self._client.log_trace(
                query={"original": self._question},
                retrieval={"strategy": "vector", "chunks": self._chunks},
                generation={"model": self._model, "answer": answer, "answered": bool(answer)},
                latency={"total_ms": total_ms},
                project={"project_id": self._project_id},
                metadata={"integration": "langchain_callback"},
            )
        except Exception as exc:  # best-effort: never break the chain
            warnings.warn(f"TraceroAI: failed to send trace: {exc}", stacklevel=2)
        finally:
            question = self._question
            self._reset()
            self._question = question  # keep for the caller to read after invoke
