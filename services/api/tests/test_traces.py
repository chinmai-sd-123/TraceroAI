from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_trace_payload() -> dict:
    return {
        "query": {
            "original": "Can admins change the workspace region themselves?",
            "rewritten": "Can admins change the workspace region themselves?",
            "rewrite_changed": False,
            "rewrite_method": "rule_based_v1",
        },
        "retrieval": {
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
                    "text": "Customers cannot directly change a workspace region after the workspace is created.",
                }
            ],
        },
        "prompt": {
            "version": "grounded_prompt_v2",
            "template_name": "grounded_answer_prompt",
        },
        "generation": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0,
            "answer": "No, admins cannot change the workspace region themselves [1].",
            "answered": True,
        },
        "latency": {
            "retrieval_ms": 17,
            "generation_ms": 1154,
            "total_ms": 1171,
        },
        "diagnosis": {
            "label": "healthy_answer",
            "reason": "The retriever found useful context and the model answered the question.",
        },
    }


def test_ingest_trace_returns_accepted() -> None:
    response = client.post("/v1/traces", json=make_trace_payload())

    assert response.status_code == 202

    body = response.json()
    assert body["status"] == "accepted"
    assert body["message"] == "Trace accepted for ingestion."
    assert "trace_id" in body


def test_ingested_trace_can_be_fetched_by_id() -> None:
    ingest_response = client.post("/v1/traces", json=make_trace_payload())
    trace_id = ingest_response.json()["trace_id"]

    get_response = client.get(f"/v1/traces/{trace_id}")

    assert get_response.status_code == 200

    trace = get_response.json()
    assert trace["trace_id"] == trace_id
    assert trace["query"]["original"] == "Can admins change the workspace region themselves?"


def test_ingest_runs_quick_evaluation_and_overwrites_diagnosis() -> None:
    ingest_response = client.post("/v1/traces", json=make_trace_payload())
    trace_id = ingest_response.json()["trace_id"]

    trace = client.get(f"/v1/traces/{trace_id}").json()

    quick = trace["evaluations"]["quick"]
    evaluator_names = {result["evaluator_name"] for result in quick}
    assert evaluator_names == {"context_relevance", "groundedness", "answer_relevance"}

    diagnosis_label = trace["diagnosis"]["label"]
    assert diagnosis_label != "pending"
    assert diagnosis_label != "healthy_answer"


def test_list_traces_includes_ingested_trace() -> None:
    ingest_response = client.post("/v1/traces", json=make_trace_payload())
    trace_id = ingest_response.json()["trace_id"]

    list_response = client.get("/v1/traces")

    assert list_response.status_code == 200

    traces = list_response.json()
    trace_ids = [trace["trace_id"] for trace in traces]

    assert trace_id in trace_ids


def test_get_missing_trace_returns_404() -> None:
    response = client.get("/v1/traces/3fa85f64-5717-4562-b3fc-2c963f66afa6")

    assert response.status_code == 404
    assert response.json() == {"detail": "Trace not found."}