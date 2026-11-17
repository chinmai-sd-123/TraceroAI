"""Send a LangGraph agent's runs to TraceroAI over OpenTelemetry.

The OpenInference LangChain instrumentor also covers LangGraph: each run of the
graph becomes spans for its nodes, model calls and tool calls, and the
OpenTelemetry exporter sends them to TraceroAI's OTLP endpoint. TraceroAI shows
each run as an agent run, step by step.

It runs without any API key: the chat model is a scripted fake that asks for a
tool, then answers. In the second run the tool fails and the agent answers
anyway, the kind of failure to look for in the steps view.

    pip install -r requirements.txt
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000/otlp
    # if your server requires keys:
    # export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <project key>"
    python app.py
"""

from typing import Annotated, Any, TypedDict

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

ORDERS = {"A-17": "Refund of $42.00 issued on 14 November to the original card."}


@tool
def lookup_order(order_id: str) -> str:
    """The latest status of an order."""
    if order_id not in ORDERS:
        raise ValueError(f"no order {order_id}")
    return ORDERS[order_id]


class ScriptedChatModel(GenericFakeChatModel):
    """A fake chat model that accepts tools, so it can stand in for a real one."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self


def ask_for_tool(order_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "lookup_order", "args": {"order_id": order_id}, "id": f"call-{order_id}"}],
    )


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def build_agent(script: list[AIMessage]):
    model = ScriptedChatModel(messages=iter(script)).bind_tools([lookup_order])

    def agent(state: State) -> dict[str, list[AnyMessage]]:
        return {"messages": [model.invoke(state["messages"])]}

    graph = StateGraph(State)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode([lookup_order], handle_tool_errors=True))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


RUNS = [
    (
        "Where is my refund for order A-17?",
        [ask_for_tool("A-17"), AIMessage(content="Your refund of $42.00 was issued on 14 November to your original card.")],
    ),
    (
        "Where is my refund for order B-90?",
        # The tool fails (there's no order B-90) and the answer ignores it.
        [ask_for_tool("B-90"), AIMessage(content="Your refund for order B-90 was issued yesterday.")],
    ),
]


def main() -> None:
    # The service name becomes the TraceroAI project when no project key is sent.
    provider = TracerProvider(resource=Resource.create({"service.name": "langgraph-agent-example"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    LangChainInstrumentor().instrument(tracer_provider=provider)

    for question, script in RUNS:
        result = build_agent(script).invoke({"messages": [HumanMessage(content=question)]})
        print(f"Q: {question}\nA: {result['messages'][-1].content}\n")

    provider.shutdown()  # sends what's left before the program exits
    print("Sent. Open the dashboard's Traces page to see both runs and their steps.")


if __name__ == "__main__":
    main()
