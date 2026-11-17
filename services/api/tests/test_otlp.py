"""OpenTelemetry ingest: OTLP/HTTP exports in both conventions become traces."""

import base64
import gzip
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from google.protobuf.json_format import ParseDict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from app.db.session import SessionLocal
from app.main import app
from app.otlp.assembly import finish_quiet
from app.schemas.traces import UsageTrace
from app.services.cost import compute_cost_usd

client = TestClient(app)

T0 = 1_763_370_000_000_000_000  # nanoseconds


def _value(v):
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, list):
        return {"arrayValue": {"values": [_value(x) for x in v]}}
    if isinstance(v, dict):
        return {"kvlistValue": {"values": [{"key": k, "value": _value(x)} for k, x in v.items()]}}
    return {"stringValue": str(v)}


def _attrs(d: dict) -> list:
    return [{"key": k, "value": _value(v)} for k, v in d.items()]


def _span(trace, span, parent, name, start_ms, end_ms, attrs, status=None):
    out = {
        "traceId": trace,
        "spanId": span,
        "name": name,
        "kind": 1,
        "startTimeUnixNano": str(T0 + start_ms * 1_000_000),
        "endTimeUnixNano": str(T0 + end_ms * 1_000_000),
        "attributes": _attrs(attrs),
    }
    if parent:
        out["parentSpanId"] = parent
    if status:
        out["status"] = status
    return out


def _export(spans, service):
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _attrs({"service.name": service, "deployment.environment.name": "staging"})},
                "scopeSpans": [{"scope": {"name": "test"}, "spans": spans}],
            }
        ]
    }


def _ids():
    trace = uuid4().hex
    return trace, [f"{i:016x}" for i in range(1, 9)]


def _openinference_rag(trace, s):
    """A LangChain retrieval QA run as the OpenInference instrumentor records it."""
    answer = "Refunds take 5 to 7 business days."
    return [
        _span(trace, s[1], s[0], "VectorStoreRetriever", 10, 200, {
            "openinference.span.kind": "RETRIEVER",
            "input.value": "refund timeline",
            "retrieval.documents.0.document.id": "d1",
            "retrieval.documents.0.document.content": "Refunds are processed within 5 to 7 business days.",
            "retrieval.documents.0.document.score": 0.91,
            "retrieval.documents.0.document.metadata": json.dumps({"source": "refunds.md"}),
            "retrieval.documents.1.document.id": "d2",
            "retrieval.documents.1.document.content": "Refunds go to the original card.",
        }),
        _span(trace, s[2], s[0], "ChatOpenAI", 210, 1400, {
            "openinference.span.kind": "LLM",
            "llm.model_name": "gpt-4o-mini",
            "llm.provider": "openai",
            "llm.token_count.prompt": 120,
            "llm.token_count.completion": 12,
            "llm.input_messages.0.message.role": "system",
            "llm.input_messages.0.message.content": "Answer from the context.",
            "llm.input_messages.1.message.role": "user",
            "llm.input_messages.1.message.content": "How long do refunds take?",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.content": answer,
            "llm.invocation_parameters": json.dumps({"temperature": 0}),
        }),
        _span(trace, s[0], None, "RetrievalQA", 0, 1500, {
            "openinference.span.kind": "CHAIN",
            "input.value": "How long do refunds take?",
            "output.value": answer,
        }),
    ]


def _gen_ai_agent(trace, s):
    """A tool-calling agent as OpenTelemetry GenAI instrumentation records it."""
    user = [{"role": "user", "parts": [{"type": "text", "content": "Where is my refund for order A-17?"}]}]
    return [
        _span(trace, s[1], s[0], "chat gpt-4o", 10, 800, {
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "openai",
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.usage.input_tokens": 300,
            "gen_ai.usage.output_tokens": 20,
            "gen_ai.input.messages": json.dumps(user),
        }),
        _span(trace, s[2], s[0], "execute_tool lookup_refund", 810, 1300, {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": "lookup_refund",
            "gen_ai.tool.call.arguments": json.dumps({"order": "A-17"}),
            "gen_ai.tool.call.result": json.dumps({"issued": "2026-11-16"}),
        }),
        _span(trace, s[3], s[0], "chat gpt-4o", 1310, 2390, {
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gpt-4o",
            "gen_ai.output.messages": json.dumps(
                [{"role": "assistant", "parts": [{"type": "text", "content": "It was issued on Monday."}]}]
            ),
        }),
        _span(trace, s[0], None, "invoke_agent support", 0, 2400, {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "support",
        }),
    ]


def _post_json(export, **headers):
    return client.post(
        "/otlp/v1/traces", content=json.dumps(export), headers={"content-type": "application/json", **headers}
    )


def _to_protobuf(export) -> bytes:
    """The same export in protobuf, where ids are bytes (base64 in proto JSON)."""
    data = json.loads(json.dumps(export))
    for rs in data["resourceSpans"]:
        for ss in rs["scopeSpans"]:
            for sp in ss["spans"]:
                for key in ("traceId", "spanId", "parentSpanId"):
                    if sp.get(key):
                        sp[key] = base64.b64encode(bytes.fromhex(sp[key])).decode()
    return ParseDict(data, ExportTraceServiceRequest()).SerializeToString()


def _trace(trace_hex):
    return client.get(f"/v1/traces/{UUID(trace_hex)}")


def _service():
    return f"otlp-{uuid4().hex[:8]}"


def test_an_openinference_rag_run_becomes_a_diagnosed_trace() -> None:
    trace, s = _ids()
    service = _service()
    response = _post_json(_export(_openinference_rag(trace, s), service))
    assert response.status_code == 200
    assert response.json() == {}

    got = _trace(trace).json()
    assert got["project"] == {"project_id": service, "environment": "staging"}
    assert got["query"]["original"] == "How long do refunds take?"
    assert got["generation"]["model"] == "gpt-4o-mini"
    assert got["generation"]["answer"] == "Refunds take 5 to 7 business days."
    assert got["generation"]["usage"]["prompt_tokens"] == 120
    chunks = got["retrieval"]["chunks"]
    assert [c["chunk_id"] for c in chunks] == ["d1", "d2"]
    assert chunks[0]["source"] == "refunds.md" and chunks[0]["final_score"] == 0.91
    assert got["latency"] == {"total_ms": 1500, "retrieval_ms": 190, "generation_ms": 1190, "prompt_build_ms": None}
    # Diagnosed like an SDK trace (the lexical check runs at ingest).
    assert got["diagnosis"]["label"] not in ("not_diagnosed", "pending")
    assert got["diagnosis"]["source"] == "lexical"
    assert got["metadata"] == {"source": "otlp", "service": service}

    steps = got["steps"]
    assert [(st["kind"], st["name"]) for st in steps] == [
        ("chain", "RetrievalQA"),
        ("retriever", "VectorStoreRetriever"),
        ("llm", "ChatOpenAI"),
    ]
    assert steps[1]["parent_id"] == steps[0]["step_id"] == s[0]
    assert steps[1]["output"]["documents"][0]["content"].startswith("Refunds are processed")
    assert steps[2]["input"]["messages"][1] == {"role": "user", "content": "How long do refunds take?"}
    assert steps[2]["attributes"]["model"] == "gpt-4o-mini"
    assert steps[2]["attributes"]["otel"]["llm.invocation_parameters"] == json.dumps({"temperature": 0})


def test_the_same_run_sent_as_protobuf_gives_the_same_trace() -> None:
    trace, s = _ids()
    response = client.post(
        "/otlp/v1/traces",
        content=_to_protobuf(_export(_openinference_rag(trace, s), _service())),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"
    reply = ExportTraceServiceResponse()
    reply.ParseFromString(response.content)
    assert reply.partial_success.rejected_spans == 0

    got = _trace(trace).json()
    assert got["generation"]["model"] == "gpt-4o-mini"
    assert [st["kind"] for st in got["steps"]] == ["chain", "retriever", "llm"]


def test_a_gen_ai_agent_run_keeps_its_steps_and_is_not_diagnosed() -> None:
    trace, s = _ids()
    service = _service()
    assert _post_json(_export(_gen_ai_agent(trace, s), service)).status_code == 200

    got = _trace(trace).json()
    assert got["generation"] is None
    assert got["diagnosis"]["label"] == "not_diagnosed"
    assert got["evaluations"]["deep_status"] == "skipped"
    assert got["query"]["original"] == "Where is my refund for order A-17?"
    steps = got["steps"]
    assert [st["kind"] for st in steps] == ["agent", "llm", "tool", "llm"]
    assert steps[0]["attributes"]["agent"] == "support"
    assert {"model": "gpt-4o", "provider": "openai", "prompt_tokens": 300}.items() <= steps[1]["attributes"].items()
    assert steps[2]["input"] == {"order": "A-17"} and steps[2]["output"] == {"issued": "2026-11-16"}
    assert steps[3]["output"] == {"messages": [{"role": "assistant", "content": "It was issued on Monday."}]}

    # Listed with its first model; counted apart from healthy and failing runs.
    listed = client.get("/v1/traces", params={"project_id": service}).json()
    assert listed[0]["generation"] is None
    summary = client.get("/v1/metrics/summary", params={"project_id": service}).json()
    assert summary["total"] == 1 and summary["not_diagnosed"] == 1 and summary["healthy"] == 0
    assert summary["by_model"] == {"gpt-4o": 1}


def test_a_run_sent_in_two_batches_becomes_one_trace_when_the_root_arrives() -> None:
    trace, s = _ids()
    service = _service()
    spans = _openinference_rag(trace, s)
    assert _post_json(_export(spans[:2], service)).status_code == 200  # children first
    assert _trace(trace).status_code == 404
    assert _post_json(_export(spans[2:], service)).status_code == 200  # then the root
    got = _trace(trace).json()
    assert len(got["steps"]) == 3 and got["generation"]["model"] == "gpt-4o-mini"


def test_a_run_whose_root_never_arrives_is_finished_once_quiet() -> None:
    trace, s = _ids()
    spans = _gen_ai_agent(trace, s)[:3]  # no root
    assert _post_json(_export(spans, _service())).status_code == 200
    assert _trace(trace).status_code == 404
    with SessionLocal() as db:
        assert finish_quiet(db, quiet_seconds=0) >= 1
    steps = _trace(trace).json()["steps"]
    assert [st["kind"] for st in steps] == ["llm", "tool", "llm"]
    assert all(st["parent_id"] is None for st in steps)  # their parent never arrived


def test_a_span_arriving_after_its_run_finished_is_appended() -> None:
    trace, s = _ids()
    service = _service()
    assert _post_json(_export(_gen_ai_agent(trace, s), service)).status_code == 200
    late = _span(trace, s[5], s[0], "guardrail check", 2395, 2399, {"openinference.span.kind": "GUARDRAIL"})
    assert _post_json(_export([late], service)).status_code == 200
    steps = _trace(trace).json()["steps"]
    assert steps[-1]["step_id"] == s[5] and steps[-1]["kind"] == "guardrail"


def test_spans_for_another_projects_trace_are_rejected() -> None:
    trace, s = _ids()
    assert _post_json(_export(_gen_ai_agent(trace, s), _service())).status_code == 200
    late = _span(trace, s[6], s[0], "intruder", 2395, 2399, {})
    response = _post_json(_export([late], _service()))
    assert response.json()["partialSuccess"]["rejectedSpans"] == 1
    assert all(st["step_id"] != s[6] for st in _trace(trace).json()["steps"])


def test_parents_that_loop_still_make_a_trace() -> None:
    trace, s = _ids()
    spans = [
        _span(trace, s[1], s[2], "a", 0, 10, {}),
        _span(trace, s[2], s[1], "b", 1, 9, {}),
    ]
    assert _post_json(_export(spans, _service())).status_code == 200
    with SessionLocal() as db:
        finish_quiet(db, quiet_seconds=0)
    steps = _trace(trace).json()["steps"]
    assert sum(st["parent_id"] is None for st in steps) == 1


def test_gzipped_bodies_are_accepted() -> None:
    trace, s = _ids()
    body = gzip.compress(json.dumps(_export(_openinference_rag(trace, s), _service())).encode())
    response = client.post(
        "/otlp/v1/traces", content=body, headers={"content-type": "application/json", "content-encoding": "gzip"}
    )
    assert response.status_code == 200
    assert _trace(trace).status_code == 200


@pytest.mark.parametrize(
    ("body", "content_type", "code"),
    [
        (b"{}", "text/plain", 415),
        (b"{not json", "application/json", 400),
        (b"\xff\xff\xff", "application/x-protobuf", 400),
    ],
    ids=["wrong type", "bad json", "bad protobuf"],
)
def test_unreadable_exports_are_refused(body, content_type, code) -> None:
    response = client.post("/otlp/v1/traces", content=body, headers={"content-type": content_type})
    assert response.status_code == code


def test_spans_with_invalid_ids_are_counted_as_rejected() -> None:
    trace, _ = _ids()
    bad = _span(trace, "not-hex", None, "x", 0, 1, {})
    response = _post_json(_export([bad], _service()))
    assert response.status_code == 200
    assert response.json()["partialSuccess"]["rejectedSpans"] == 1


def test_model_calls_are_priced_and_summed_into_the_run_cost() -> None:
    trace, s = _ids()
    service = _service()
    spans = _gen_ai_agent(trace, s)
    spans[2]["attributes"] += _attrs({"gen_ai.usage.input_tokens": 340, "gen_ai.usage.output_tokens": 9})
    assert _post_json(_export(spans, service)).status_code == 200

    first = compute_cost_usd("gpt-4o", UsageTrace(prompt_tokens=300, completion_tokens=20))
    second = compute_cost_usd("gpt-4o", UsageTrace(prompt_tokens=340, completion_tokens=9))
    assert first and second
    got = _trace(trace).json()
    calls = [st for st in got["steps"] if st["kind"] == "llm"]
    assert [st["attributes"]["cost_usd"] for st in calls] == [first, second]
    assert got["run_usage"] == {
        "prompt_tokens": 640,
        "completion_tokens": 29,
        "total_tokens": 669,
        "cost_usd": pytest.approx(first + second),
    }

    summary = client.get("/v1/metrics/summary", params={"project_id": service}).json()
    assert summary["cost_usd"]["priced"] == 1
    assert summary["cost_usd"]["total"] == pytest.approx(first + second)
    assert summary["cost_usd"]["per_healthy"] is None  # an agent run is never a healthy answer


def test_a_run_with_an_unpriced_model_call_has_no_cost() -> None:
    trace, s = _ids()
    service = _service()
    spans = _gen_ai_agent(trace, s)
    spans[2]["attributes"] = [a for a in spans[2]["attributes"] if a["key"] != "gen_ai.request.model"]
    spans[2]["attributes"] += _attrs(
        {"gen_ai.request.model": "acme-house-model", "gen_ai.usage.input_tokens": 50, "gen_ai.usage.output_tokens": 5}
    )
    assert _post_json(_export(spans, service)).status_code == 200

    got = _trace(trace).json()
    calls = [st for st in got["steps"] if st["kind"] == "llm"]
    assert "cost_usd" in calls[0]["attributes"] and "cost_usd" not in calls[1]["attributes"]
    # Tokens still add up; the cost doesn't, rather than understate the run.
    assert got["run_usage"]["total_tokens"] == 375 and got["run_usage"]["cost_usd"] is None
    summary = client.get("/v1/metrics/summary", params={"project_id": service}).json()
    assert summary["cost_usd"]["priced"] == 0


def test_cost_per_healthy_answer_includes_what_failed_runs_spent() -> None:
    service = _service()
    rag_runs = []
    for _ in range(2):
        trace, s = _ids()
        rag_runs.append(UUID(trace))
        assert _post_json(_export(_openinference_rag(trace, s), service)).status_code == 200
    # The judge's verdict (the lexical estimate can't call an answer healthy).
    with SessionLocal() as db:
        db.execute(
            text("UPDATE traces SET diagnosis_label = 'healthy_answer' WHERE trace_id = ANY(:ids)"), {"ids": rag_runs}
        )
        db.commit()
    trace, s = _ids()
    assert _post_json(_export(_gen_ai_agent(trace, s), service)).status_code == 200

    rag = compute_cost_usd("gpt-4o-mini", UsageTrace(prompt_tokens=120, completion_tokens=12))
    agent = compute_cost_usd("gpt-4o", UsageTrace(prompt_tokens=300, completion_tokens=20))
    assert rag and agent
    summary = client.get("/v1/metrics/summary", params={"project_id": service}).json()
    assert summary["healthy"] == 2
    assert summary["cost_usd"]["priced"] == 3
    assert summary["cost_usd"]["per_healthy"] == pytest.approx((2 * rag + agent) / 2)


def _langgraph_agent(trace, s):
    """A LangGraph agent as the OpenInference LangChain instrumentor records it:
    the graph's state as input, a tool call, a tool that fails, and an answer."""
    state = {"messages": [{"type": "human", "data": {"type": "human", "content": "Where is my refund for order B-90?"}}]}
    traceback = (
        "ValueError('no order B-90')Traceback (most recent call last):\n"
        '  File "C:\\Users\\someone\\app.py", line 40, in lookup_order\nValueError: no order B-90'
    )
    return [
        _span(trace, s[0], None, "LangGraph", 0, 900, {
            "openinference.span.kind": "CHAIN",
            "input.value": json.dumps(state),
            "input.mime_type": "application/json",
        }),
        _span(trace, s[1], s[0], "ScriptedChatModel", 10, 200, {
            "openinference.span.kind": "LLM",
            "llm.input_messages.0.message.role": "user",
            "llm.input_messages.0.message.content": "Where is my refund for order B-90?",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.tool_calls.0.tool_call.function.name": "lookup_order",
            "llm.output_messages.0.message.tool_calls.0.tool_call.function.arguments": json.dumps({"order_id": "B-90"}),
        }),
        _span(trace, s[2], s[0], "lookup_order", 210, 300, {
            "openinference.span.kind": "TOOL",
            "tool.name": "lookup_order",
            "input.value": "B-90",
        }, status={"code": 2, "message": traceback}),
        _span(trace, s[3], s[0], "lookup_order", 310, 400, {
            "openinference.span.kind": "TOOL",
            "tool.name": "lookup_order",
            "input.value": "A-17",
            "output.value": json.dumps({"type": "tool", "data": {"type": "tool", "content": "Refund issued.", "status": "success"}}),
            "output.mime_type": "application/json",
        }),
    ]


def test_a_langgraph_run_reads_its_question_tool_calls_and_tool_results() -> None:
    trace, s = _ids()
    assert _post_json(_export(_langgraph_agent(trace, s), _service())).status_code == 200

    got = _trace(trace).json()
    # The question, not the graph's serialized state.
    assert got["query"]["original"] == "Where is my refund for order B-90?"
    steps = {st["step_id"]: st for st in got["steps"]}
    assert steps[s[1]]["output"]["messages"] == [
        {"role": "assistant", "content": None, "tool_calls": [{"name": "lookup_order", "arguments": {"order_id": "B-90"}}]}
    ]
    # The error without the traceback (and the host's file paths in it).
    assert steps[s[2]]["status"] == "error"
    assert steps[s[2]]["status_message"] == "ValueError('no order B-90')"
    # What the tool returned, not LangChain's message wrapping it.
    assert steps[s[3]]["output"] == "Refund issued."


def test_gen_ai_tool_calls_are_read_from_message_parts() -> None:
    trace, s = _ids()
    spans = _gen_ai_agent(trace, s)
    call = [{"role": "assistant", "parts": [{"type": "tool_call", "name": "lookup_refund", "arguments": {"order": "A-17"}}]}]
    spans[0]["attributes"] += _attrs({"gen_ai.output.messages": json.dumps(call)})
    assert _post_json(_export(spans, _service())).status_code == 200

    first_call = _trace(trace).json()["steps"][1]
    assert first_call["output"]["messages"] == [
        {"role": "assistant", "content": None, "tool_calls": [{"name": "lookup_refund", "arguments": {"order": "A-17"}}]}
    ]
