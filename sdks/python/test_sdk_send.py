from traceroai import TraceroClient

client = TraceroClient(base_url="http://127.0.0.1:8000")

trace_id = client.log_trace(
    query={
        "original": "Can admins change the workspace region themselves?",
        "rewritten": "Can admins change the workspace region themselves?",
        "rewrite_changed": False,
        "rewrite_method": "rule_based_v1",
    },
    retrieval={
        "strategy": "hybrid_rrf_rerank",
        "config": {
            "lexical_top_k": 5,
            "dense_top_k": 5,
            "final_top_k": 3,
            "fusion": "rrf",
            "reranker": "rule_based_v1",
        },
        "chunks": [
            {
                "rank": 1,
                "chunk_id": "product_faq_2",
                "document_id": "product_faq",
                "document_title": "Product FAQ",
                "section": "Can I change my workspace region?",
                "source": "product_faq.md",
                "final_score": 1.08,
                "text": "Customers cannot directly change a workspace region after the workspace is created. To request a region change, customers must contact support.",
            }
        ],
    },
    generation={
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0,
        "answer": "No, admins cannot change the workspace region themselves. They must contact support [1].",
        "answered": True,
    },
    latency={
        "retrieval_ms": 17,
        "generation_ms": 1154,
        "total_ms": 1171,
    },
    diagnosis={
        "label": "healthy_answer",
        "reason": "The retriever found useful context and the model answered the question.",
    },
)

print(f"Sent trace: {trace_id}")