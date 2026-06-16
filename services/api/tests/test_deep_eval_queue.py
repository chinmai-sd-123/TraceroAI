from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.services.deep_eval_queue import enqueue_deep_eval_request

client = TestClient(app)

def test_enqueue_returns_false_without_redis() -> None:
    # conftest forces redis_url=None, so Redis is unconfigured -> caller falls back.
    assert enqueue_deep_eval_request(uuid4()) is False


def test_ingest_uses_queue_and_skips_background_when_enqueue_succeeds(monkeypatch) -> None:
    # Simulate Redis accepting the job. The route must NOT also run deep eval
    # in-process — so with no worker running in tests, deep stays empty.
    monkeypatch.setattr(
        "app.api.routes.traces.enqueue_deep_eval_request", lambda trace_id: True
    )

    payload = {
        "query": {"original": "Can admins change the workspace region?"},
        "retrieval": {
            "chunks": [
                {"rank": 1, "chunk_id": "c1", "text": "Customers cannot change a region after creation."}
            ]
        },
        "generation": {"model": "gpt-4o-mini", "answer": "No, admins cannot."},
    }
    trace_id = client.post("/v1/traces", json=payload).json()["trace_id"]

    deep = client.get(f"/v1/traces/{trace_id}").json()["evaluations"]["deep"]
    assert deep == []