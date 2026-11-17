"""Send a LangChain RAG app's runs to TraceroAI over OpenTelemetry.

No TraceroAI SDK and no change to the chain: the OpenInference instrumentor
records each run as spans, and the OpenTelemetry exporter sends them to
TraceroAI's OTLP endpoint. TraceroAI turns each run into a trace, sees the
retrieval and the model's answer, and diagnoses it.

It runs without any API key: the chat model is LangChain's fake one, answering
from a fixed list, and the retriever is a keyword match over three documents.
The second answer claims something the documents don't say, so it should come
back with a grounding problem.

    pip install -r requirements.txt
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:8000/otlp
    # if your server requires keys:
    # export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <project key>"
    python app.py
"""

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnablePassthrough
from openinference.instrumentation.langchain import LangChainInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

DOCUMENTS = [
    Document(
        page_content="Refunds are processed within 5 to 7 business days after the request is approved.",
        metadata={"source": "refund-policy.md", "id": "refund-timing"},
    ),
    Document(
        page_content="Refunds are always issued to the original payment method used for the purchase.",
        metadata={"source": "refund-policy.md", "id": "refund-method"},
    ),
    Document(
        page_content="The Pro plan includes unlimited projects and email support.",
        metadata={"source": "plans.md", "id": "pro-plan"},
    ),
]


class KeywordRetriever(BaseRetriever):
    """The two documents containing the most of the question's longer words."""

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> list[Document]:
        words = [w.strip("?.,!").lower() for w in query.split() if len(w.strip("?.,!")) > 3]
        ranked = sorted(DOCUMENTS, key=lambda d: -sum(w in d.page_content.lower() for w in words))
        return ranked[:2]


def main() -> None:
    # The service name becomes the TraceroAI project when no project key is sent.
    provider = TracerProvider(resource=Resource.create({"service.name": "langchain-rag-example"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # reads OTEL_EXPORTER_OTLP_*
    LangChainInstrumentor().instrument(tracer_provider=provider)

    prompt = ChatPromptTemplate.from_messages(
        [("system", "Answer using only this context:\n{context}"), ("human", "{question}")]
    )
    model = FakeListChatModel(
        responses=[
            "Refunds are processed within 5 to 7 business days after approval.",
            "Yes, the Pro plan includes unlimited projects, email support and a dedicated account manager.",
        ]
    )
    chain = (
        {"context": KeywordRetriever() | (lambda docs: "\n".join(d.page_content for d in docs)), "question": RunnablePassthrough()}
        | prompt
        | model
        | StrOutputParser()
    )

    for question in ["How long does a refund take?", "What does the Pro plan include?"]:
        print(f"{question}\n  -> {chain.invoke(question)}")

    provider.shutdown()  # send any spans still waiting in the batch


if __name__ == "__main__":
    main()
