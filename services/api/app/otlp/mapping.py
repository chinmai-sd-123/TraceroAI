"""One OpenTelemetry span as one TraceroAI step.

Two conventions are read, whichever the instrumentation used:

- OpenInference (Arize; the LangChain, LlamaIndex and OpenAI instrumentors):
  openinference.span.kind, input.value, output.value, llm.*, retrieval.documents,
  tool.*. Lists are flattened with indices, e.g. llm.input_messages.0.message.role.
- OpenTelemetry GenAI (gen_ai.*). Still marked "Development", so names move;
  older names are read alongside newer ones.

Each field is taken from the first key in its list that's present, so a
convention renaming an attribute is a one-line change below. Attributes that
aren't lifted into the step's input, output or summary are kept, under "otel".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.otlp.decode import STATUS_ERROR, STATUS_OK, OtlpSpan
from app.schemas.steps import STEP_NAME_MAX_LENGTH, StepIn, StepKind

OPENINFERENCE_KINDS: dict[str, StepKind] = {
    "LLM": "llm",
    "CHAIN": "chain",
    "RETRIEVER": "retriever",
    "TOOL": "tool",
    "AGENT": "agent",
    "EMBEDDING": "embedding",
    "RERANKER": "reranker",
    "GUARDRAIL": "guardrail",
}
GEN_AI_OPERATIONS: dict[str, StepKind] = {
    "chat": "llm",
    "text_completion": "llm",
    "generate_content": "llm",
    "realtime_inference": "llm",
    "embeddings": "embedding",
    "execute_tool": "tool",
    "invoke_agent": "agent",
    "create_agent": "agent",
    "invoke_workflow": "agent",
    "plan": "agent",
    "retrieval": "retriever",
}

# Summary attributes: (name on the step, keys to read in order).
SUMMARY_KEYS: list[tuple[str, tuple[str, ...]]] = [
    ("model", ("llm.response.model_name", "llm.model_name", "gen_ai.response.model", "gen_ai.request.model", "embedding.model_name")),
    ("provider", ("llm.provider", "llm.system", "gen_ai.provider.name", "gen_ai.system")),
    ("prompt_tokens", ("llm.token_count.prompt", "gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens")),
    ("completion_tokens", ("llm.token_count.completion", "gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens")),
    ("total_tokens", ("llm.token_count.total",)),
    ("cost_usd", ("llm.cost.total",)),
    ("temperature", ("gen_ai.request.temperature",)),
    ("tool", ("tool.name", "gen_ai.tool.name")),
    ("agent", ("agent.name", "gen_ai.agent.name")),
    ("prompt_version", ("llm.prompt_template.version", "gen_ai.prompt.version")),
    ("session_id", ("session.id", "gen_ai.conversation.id")),
    ("user_id", ("user.id",)),
]

# Lifted into input or output; not repeated under "otel".
CONTENT_PREFIXES = (
    "input.",
    "output.",
    "llm.input_messages.",
    "llm.output_messages.",
    "retrieval.documents.",
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.system_instructions",
    "gen_ai.retrieval.documents",
    "gen_ai.retrieval.query.text",
    "gen_ai.tool.call.arguments",
    "gen_ai.tool.call.result",
    "tool.parameters",
)


def span_to_step(span: OtlpSpan) -> StepIn:
    attrs = span.attributes
    kind = step_kind(attrs)
    started = _time(span.start_ns)
    ended = _time(span.end_ns) if span.end_ns else None
    if ended is not None and ended < started:
        ended = started

    summary = {name: value for name, keys in SUMMARY_KEYS if (value := _first(attrs, keys)) is not None}
    lifted = {key for _, keys in SUMMARY_KEYS for key in keys}
    otel = {
        key: value
        for key, value in attrs.items()
        if key not in lifted and key != "openinference.span.kind" and not key.startswith(CONTENT_PREFIXES)
    }
    if otel:
        summary["otel"] = otel

    return StepIn(
        step_id=span.span_id,
        parent_id=span.parent_span_id,
        kind=kind,
        name=span.name[:STEP_NAME_MAX_LENGTH] or "span",
        started_at=started,
        ended_at=ended,
        status="error" if span.status_code == STATUS_ERROR else "ok" if span.status_code == STATUS_OK else "unset",
        status_message=_error_message(span),
        input=_input(kind, attrs),
        output=_output(kind, attrs),
        attributes=summary,
    )


def step_kind(attrs: dict[str, Any]) -> StepKind:
    openinference = attrs.get("openinference.span.kind")
    if isinstance(openinference, str) and openinference.upper() in OPENINFERENCE_KINDS:
        return OPENINFERENCE_KINDS[openinference.upper()]
    operation = attrs.get("gen_ai.operation.name")
    if isinstance(operation, str) and operation in GEN_AI_OPERATIONS:
        return GEN_AI_OPERATIONS[operation]
    return "chain"


# --- content ---------------------------------------------------------------


def _input(kind: StepKind, attrs: dict[str, Any]) -> Any:
    if kind == "llm":
        messages = messages_from(attrs, "llm.input_messages", "gen_ai.input.messages")
        if messages:
            return {"messages": messages}
    if kind == "retriever":
        query = _first(attrs, ("gen_ai.retrieval.query.text",))
        if query is not None:
            return query
    if kind == "tool":
        arguments = _first(attrs, ("gen_ai.tool.call.arguments", "tool.parameters"))
        if arguments is not None:
            return _maybe_json(arguments)
    return _value(attrs, "input")


def _output(kind: StepKind, attrs: dict[str, Any]) -> Any:
    if kind == "llm":
        messages = messages_from(attrs, "llm.output_messages", "gen_ai.output.messages")
        if messages:
            return {"messages": messages}
    if kind == "retriever":
        documents = documents_from(attrs)
        if documents:
            return {"documents": documents}
    if kind == "tool":
        result = _first(attrs, ("gen_ai.tool.call.result",))
        if result is not None:
            return _maybe_json(result)
        return _tool_result(_value(attrs, "output"))
    return _value(attrs, "output")


def _tool_result(value: Any) -> Any:
    """A tool's result. LangChain records the ToolMessage that wraps it
    ({type: "tool", data: {content}}); the content is what the tool returned."""
    if isinstance(value, dict):
        data = value.get("data") if isinstance(value.get("data"), dict) else value.get("kwargs")
        if isinstance(data, dict) and data.get("type", value.get("type")) == "tool" and "content" in data:
            return _maybe_json(data["content"])
    return value


def _value(attrs: dict[str, Any], prefix: str) -> Any:
    """OpenInference input.value / output.value, parsed when it's JSON."""
    value = attrs.get(f"{prefix}.value")
    if value is None:
        return None
    if attrs.get(f"{prefix}.mime_type") == "application/json":
        return _maybe_json(value)
    return value


def messages_from(attrs: dict[str, Any], flattened: str, gen_ai: str) -> list[dict[str, Any]]:
    """Chat messages as [{role, content}], from either convention. A message
    that calls tools also has tool_calls: [{name, arguments}]."""
    found = []
    for item in indexed(attrs, flattened):
        role = item.get("message.role")
        content = item.get("message.content")
        if content is None:  # multi-part content: message.contents.N.message_content.text
            parts = indexed(item, "message.contents")
            texts = [str(p["message_content.text"]) for p in parts if p.get("message_content.text")]
            content = "\n".join(texts) if texts else None
        calls = [
            _tool_call(call.get("tool_call.function.name"), call.get("tool_call.function.arguments"))
            for call in indexed(item, "message.tool_calls")
            if call.get("tool_call.function.name")
        ]
        if role is not None or content is not None or calls:
            found.append({"role": role, "content": content, **({"tool_calls": calls} if calls else {})})
    if found:
        return found
    raw = _maybe_json(attrs.get(gen_ai))
    if isinstance(raw, list):
        for message in raw:
            if not isinstance(message, dict):
                continue
            parts = [p for p in message.get("parts") or [] if isinstance(p, dict)]
            texts = [p.get("content") for p in parts if p.get("type") == "text"]
            calls = [
                _tool_call(p.get("name"), p.get("arguments"))
                for p in parts
                if p.get("type") == "tool_call" and p.get("name")
            ]
            found.append(
                {
                    "role": message.get("role"),
                    "content": "\n".join(t for t in texts if isinstance(t, str)) or None,
                    **({"tool_calls": calls} if calls else {}),
                }
            )
    return found


def _tool_call(name: Any, arguments: Any) -> dict[str, Any]:
    """A tool the model asked to call, with its arguments parsed when they're JSON."""
    return {"name": str(name), "arguments": _maybe_json(arguments)}


def documents_from(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """Retrieved documents as [{id, content, score, metadata}]. OpenInference
    records their text; OpenTelemetry GenAI only an id and a score."""
    documents = []
    for item in indexed(attrs, "retrieval.documents"):
        documents.append(
            {
                "id": item.get("document.id"),
                "content": item.get("document.content"),
                "score": item.get("document.score"),
                "metadata": _maybe_json(item.get("document.metadata")),
            }
        )
    if documents:
        return documents
    raw = _maybe_json(attrs.get("gen_ai.retrieval.documents"))
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                documents.append({"id": item.get("id"), "content": item.get("content"), "score": item.get("score"), "metadata": None})
    return documents


def indexed(attrs: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    """Unflatten prefix.N.rest keys into a list of {rest: value}, ordered by N."""
    marker = prefix + "."
    groups: dict[int, dict[str, Any]] = {}
    for key, value in attrs.items():
        if not key.startswith(marker):
            continue
        index, _, rest = key[len(marker):].partition(".")
        if index.isdigit() and rest:
            groups.setdefault(int(index), {})[rest] = value
    return [groups[i] for i in sorted(groups)]


def _error_message(span: OtlpSpan) -> str | None:
    if span.status_message:
        # Some instrumentations append the whole Python traceback (with the
        # host's file paths); the stack trace stays in the exception event.
        message = span.status_message.split("Traceback (most recent call last)")[0].strip()
        return (message or span.status_message)[:2000]
    if span.status_code == STATUS_ERROR:
        for event in span.events:
            if event.get("name") == "exception":
                message = event["attributes"].get("exception.message") or event["attributes"].get("exception.type")
                if message:
                    return str(message)[:2000]
    return None


def _first(attrs: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if attrs.get(key) is not None:
            return attrs[key]
    return None


def _maybe_json(value: Any) -> Any:
    if isinstance(value, str) and value[:1] in ("{", "["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _time(nanoseconds: int) -> datetime:
    return datetime.fromtimestamp(nanoseconds / 1e9, tz=UTC)
