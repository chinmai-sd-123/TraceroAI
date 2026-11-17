"""Decode an OTLP/HTTP trace export into plain spans.

OTLP/HTTP sends an ExportTraceServiceRequest either as protobuf
(application/x-protobuf) or as JSON (application/json), optionally gzipped.
Both are turned into the same OtlpSpan list here, so nothing downstream cares
which one arrived. The JSON encoding differs from protobuf's own JSON mapping in
one way that matters: trace and span ids are hex, not base64.
https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding
"""

from __future__ import annotations

import base64
import binascii
import json
import zlib
from dataclasses import dataclass, field
from typing import Any

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest


class OtlpDecodeError(ValueError):
    """The body isn't a readable OTLP trace export."""


class UnsupportedMediaType(OtlpDecodeError):
    """Neither protobuf nor JSON."""


class TooLarge(OtlpDecodeError):
    """The body unpacks to more than the request size limit."""


# Span status codes (opentelemetry.proto.trace.v1.Status.StatusCode).
STATUS_UNSET, STATUS_OK, STATUS_ERROR = 0, 1, 2


@dataclass
class OtlpSpan:
    trace_id: str  # 32 lowercase hex characters
    span_id: str  # 16 lowercase hex characters
    parent_span_id: str | None
    name: str
    start_ns: int
    end_ns: int | None
    status_code: int
    status_message: str | None
    attributes: dict[str, Any]
    events: list[dict[str, Any]] = field(default_factory=list)
    resource: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decoded:
    spans: list[OtlpSpan]
    rejected: int  # spans dropped for invalid ids


def decode(body: bytes, *, content_type: str | None, content_encoding: str | None, max_bytes: int) -> Decoded:
    if (content_encoding or "").strip().lower() == "gzip":
        body = _gunzip(body, max_bytes)
    media = (content_type or "").split(";")[0].strip().lower()
    if media == "application/x-protobuf":
        message = ExportTraceServiceRequest()
        try:
            message.ParseFromString(body)
        except DecodeError as exc:
            raise OtlpDecodeError(f"not an OTLP protobuf trace export: {exc}") from exc
        data = MessageToDict(message, use_integers_for_enums=True)
        return _spans(data, ids="base64")
    if media == "application/json":
        try:
            data = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OtlpDecodeError(f"not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise OtlpDecodeError("the JSON body must be an object with resourceSpans")
        return _spans(data, ids="hex")
    raise UnsupportedMediaType(f"send application/x-protobuf or application/json, not {media or 'nothing'}")


def _gunzip(body: bytes, max_bytes: int) -> bytes:
    # Bounded, so a small gzip bomb can't expand into gigabytes.
    unpacker = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = unpacker.decompress(body, max_bytes + 1)
    except zlib.error as exc:
        raise OtlpDecodeError(f"not valid gzip: {exc}") from exc
    if len(out) > max_bytes or unpacker.unconsumed_tail:
        raise TooLarge(f"the body unpacks to more than {max_bytes} bytes")
    return out


def _spans(data: dict[str, Any], *, ids: str) -> Decoded:
    spans: list[OtlpSpan] = []
    rejected = 0
    for resource_spans in data.get("resourceSpans") or []:
        resource = attributes((resource_spans.get("resource") or {}).get("attributes"))
        for scope_spans in resource_spans.get("scopeSpans") or []:
            for raw in scope_spans.get("spans") or []:
                trace_id = _id(raw.get("traceId"), ids, 16)
                span_id = _id(raw.get("spanId"), ids, 8)
                if trace_id is None or span_id is None:
                    rejected += 1
                    continue
                status = raw.get("status") or {}
                end = _int(raw.get("endTimeUnixNano"))
                spans.append(
                    OtlpSpan(
                        trace_id=trace_id,
                        span_id=span_id,
                        parent_span_id=_id(raw.get("parentSpanId"), ids, 8),
                        name=str(raw.get("name") or "span"),
                        start_ns=_int(raw.get("startTimeUnixNano")) or 0,
                        end_ns=end or None,
                        status_code=_int(status.get("code")) or STATUS_UNSET,
                        status_message=status.get("message") or None,
                        attributes=attributes(raw.get("attributes")),
                        events=[
                            {"name": event.get("name"), "attributes": attributes(event.get("attributes"))}
                            for event in raw.get("events") or []
                        ],
                        resource=resource,
                    )
                )
    return Decoded(spans=spans, rejected=rejected)


def _id(value: Any, encoding: str, size: int) -> str | None:
    """An id as lowercase hex, or None when it's missing, malformed or all zeros."""
    if not value or not isinstance(value, str):
        return None
    try:
        raw = base64.b64decode(value, validate=True) if encoding == "base64" else bytes.fromhex(value)
    except (binascii.Error, ValueError):
        return None
    if len(raw) != size or not any(raw):
        return None
    return raw.hex()


def _int(value: Any) -> int | None:
    """OTLP 64-bit integers arrive as JSON strings or numbers."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def attributes(items: Any) -> dict[str, Any]:
    """OTLP key-value pairs as a plain dict."""
    result: dict[str, Any] = {}
    for item in items or []:
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            result[item["key"]] = any_value(item.get("value"))
    return result


def any_value(value: Any) -> Any:
    """An OTLP AnyValue as a plain Python value."""
    if not isinstance(value, dict):
        return None
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "intValue" in value:
        return _int(value["intValue"])
    if "doubleValue" in value:
        try:
            return float(value["doubleValue"])
        except (TypeError, ValueError):
            return None
    if "arrayValue" in value:
        return [any_value(item) for item in (value["arrayValue"] or {}).get("values") or []]
    if "kvlistValue" in value:
        return attributes((value["kvlistValue"] or {}).get("values"))
    if "bytesValue" in value:
        return value["bytesValue"]  # base64, kept as text
    return None
