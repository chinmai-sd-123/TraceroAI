"""A finished run's steps as a trace.

When the run retrieved documents with their text and a model then answered,
it's a RAG run: the retrieval and answer become the trace's RAG fields and it's
diagnosed like a trace from the SDK. Otherwise (an agent, or retrieval recorded
without document text, as OpenTelemetry GenAI does) the trace keeps its steps
and is NOT_DIAGNOSED.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.schemas.steps import StepIn
from app.schemas.traces import (
    GenerationTrace,
    LatencyTrace,
    ProjectInfo,
    PromptTrace,
    QueryTrace,
    RetrievalTrace,
    RetrievedChunk,
    Trace,
    UsageTrace,
)
from app.schemas.validation import MAX_CHUNKS_PER_TRACE, MODEL_MAX_LENGTH

QUERY_MAX_LENGTH = 10_000


def order_and_root(steps: list[StepIn]) -> list[StepIn]:
    """Steps in start order, with parents that never arrived (another service's
    span, or one dropped by the exporter) cleared, so the steps form a tree."""
    ordered = sorted(steps, key=lambda step: step.started_at)
    by_id = {step.step_id: step for step in ordered}
    for step in ordered:
        if step.parent_id is not None and step.parent_id not in by_id:
            step.parent_id = None
    # A malformed export can loop (a's parent b, b's parent a): cut each loop at
    # the step where the walk comes back round, so there is always a root.
    for step in ordered:
        seen = {step.step_id}
        current = step
        while current.parent_id is not None:
            if current.parent_id in seen:
                current.parent_id = None
                break
            seen.add(current.parent_id)
            current = by_id[current.parent_id]
    return ordered


def build_trace(
    trace_id: str, steps: list[StepIn], *, project_id: str, environment: str, resource: dict[str, Any]
) -> Trace:
    """steps must already be ordered (order_and_root)."""
    root = next(step for step in steps if step.parent_id is None)
    retriever, llm = _rag_pair(steps)

    first_llm = next((step for step in steps if step.kind == "llm"), None)
    query = _text(root.input) or (_user_text(first_llm.input) if first_llm else None) or root.name
    total_ms = _ms(root)
    service = resource.get("service.name")
    metadata: dict[str, Any] = {"source": "otlp"}
    if isinstance(service, str):
        metadata["service"] = service

    trace = Trace(
        trace_id=UUID(trace_id),
        timestamp=root.started_at,
        status="answered" if llm else ("error" if root.status == "error" else "completed"),
        project=ProjectInfo(project_id=project_id, environment=environment),
        query=QueryTrace(original=query[:QUERY_MAX_LENGTH]),
        latency=LatencyTrace(total_ms=total_ms),
        metadata=metadata,
    )
    if retriever is None or llm is None:
        return trace

    documents = [doc for doc in retriever.output["documents"] if _has_text(doc)][:MAX_CHUNKS_PER_TRACE]
    retriever_query = _text(retriever.input)
    if retriever_query:
        trace.query = QueryTrace(original=query[:QUERY_MAX_LENGTH], rewritten=retriever_query[:QUERY_MAX_LENGTH])
    trace.retrieval = RetrievalTrace(
        strategy=retriever.name[:100],
        chunks=[
            RetrievedChunk(
                rank=i + 1,
                chunk_id=str(doc.get("id") or _meta(doc, "id", "chunk_id") or f"{retriever.step_id}-{i + 1}"),
                document_id=_meta(doc, "document_id", "doc_id", "id"),
                document_title=_meta(doc, "title", "document_title"),
                source=_meta(doc, "source", "file_path", "url"),
                final_score=doc["score"] if isinstance(doc.get("score"), int | float) else None,
                text=doc["content"],
            )
            for i, doc in enumerate(documents)
        ],
    )
    attributes = llm.attributes
    answer = _assistant_text(llm.output) or ""  # never empty: _rag_pair requires an answer
    trace.generation = GenerationTrace(
        provider=_str(attributes.get("provider")),
        model=(_str(attributes.get("model")) or "unknown")[:MODEL_MAX_LENGTH],
        temperature=attributes["temperature"] if isinstance(attributes.get("temperature"), int | float) else None,
        answer=answer,
        usage=UsageTrace(
            prompt_tokens=_count(attributes.get("prompt_tokens")),
            completion_tokens=_count(attributes.get("completion_tokens")),
            total_tokens=_count(attributes.get("total_tokens")),
        ),
    )
    trace.prompt = PromptTrace(version=_str(attributes.get("prompt_version")))
    trace.latency = LatencyTrace(total_ms=total_ms, retrieval_ms=_ms(retriever), generation_ms=_ms(llm))
    return trace


def _rag_pair(steps: list[StepIn]) -> tuple[StepIn | None, StepIn | None]:
    """The last retrieval that returned document text, and the last model call
    after it that produced an answer."""
    retriever = None
    for step in steps:
        if step.kind == "retriever" and isinstance(step.output, dict) and any(
            _has_text(doc) for doc in step.output.get("documents") or []
        ):
            retriever = step
    if retriever is None:
        return None, None
    llm = None
    for step in steps:
        if step.kind == "llm" and step.started_at >= retriever.started_at and _assistant_text(step.output):
            llm = step
    return (retriever, llm) if llm else (None, None)


def _has_text(document: Any) -> bool:
    return isinstance(document, dict) and isinstance(document.get("content"), str) and bool(document["content"].strip())


def _assistant_text(output: Any) -> str | None:
    if isinstance(output, dict) and isinstance(output.get("messages"), list):
        texts = [str(m["content"]) for m in output["messages"] if isinstance(m, dict) and isinstance(m.get("content"), str)]
        return "\n".join(texts) or None
    return _text(output)


def _user_text(value: Any) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("messages"), list):
        users = [m.get("content") for m in value["messages"] if isinstance(m, dict) and m.get("role") == "user"]
        texts = [t for t in users if isinstance(t, str) and t.strip()]
        return texts[-1] if texts else None
    return _text(value)


def _text(value: Any) -> str | None:
    """A readable text from a step's input or output."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("question", "query", "input", "text", "answer", "output", "result", "content"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
        messages = _user_text(value) if "messages" in value else None
        if messages:
            return messages
    if value is not None:
        rendered = json.dumps(value, ensure_ascii=False, default=str)
        return rendered if rendered not in ("{}", "[]", "null") else None
    return None


def _meta(document: dict[str, Any], *keys: str) -> str | None:
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        return None
    for key in keys:
        if metadata.get(key) is not None:
            return str(metadata[key])[:500]
    return None


def _ms(step: StepIn) -> int | None:
    if step.ended_at is None:
        return None
    return max(0, round((step.ended_at - step.started_at).total_seconds() * 1000))


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
