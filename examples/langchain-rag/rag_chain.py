"""A real LangChain LCEL RAG pipeline (OpenAI), built once and reused by the
TraceroAI integration examples.

Pipeline: in-memory vector retriever -> prompt -> ChatOpenAI -> string output.
Exposes the individual steps (retriever, prompt, llm) so the explicit-tracing
example can log each stage, plus a composed `chain` for the decorator example.
"""

from __future__ import annotations

import os

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from knowledge_base import DOCUMENTS

# Models. OPENAI_API_KEY is read from the environment by the LangChain clients.
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
TOP_K = int(os.getenv("RAG_TOP_K", "3"))

PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You answer questions using ONLY the provided context. Cite sources "
            "like [1]. If the context does not contain the answer, say you don't "
            "know based on the provided context.",
        ),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)


def build_retriever():
    """Embed the KB into an in-memory vector store and return a retriever."""
    docs = [
        Document(page_content=d["text"], metadata={"title": d["title"], "id": d["id"]})
        for d in DOCUMENTS
    ]
    store = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings(model=EMBED_MODEL))
    return store.as_retriever(search_kwargs={"k": TOP_K})


def format_context(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i + 1}] {d.page_content}" for i, d in enumerate(docs))


def docs_to_chunks(docs: list[Document]) -> list[dict]:
    """Convert LangChain Documents to the TraceroAI retrieval-chunk shape."""
    return [
        {
            "rank": i + 1,
            "chunk_id": d.metadata.get("id", f"chunk_{i + 1}"),
            "document_title": d.metadata.get("title", "Untitled"),
            "text": d.page_content,
        }
        for i, d in enumerate(docs)
    ]


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(model=CHAT_MODEL, temperature=0)


def build_chain():
    """A composed LCEL chain: {question} -> retrieve -> prompt -> llm -> text."""
    retriever = build_retriever()
    llm = build_llm()

    return (
        {
            "context": retriever | format_context,
            "question": lambda x: x,
        }
        | PROMPT
        | llm
        | StrOutputParser()
    )
