from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def make_trace_payload() -> dict:
    return {
        "query": {"original": "How are refunds issued?"},
        "retrieval": {
            "chunks": [
                {
                    "rank": 1,
                    "chunk_id": "r1",
                    "text": "Refunds go to the original payment method.",
                }
            ]
        },
        "generation": {
            "model": "gpt-4o-mini",
            "answer": "Refunds go to your original payment method.",
        },
    }


def _ingest() -> str:
    return client.post("/v1/traces", json=make_trace_payload()).json()["trace_id"]


def test_add_feedback_persists_on_trace() -> None:
    trace_id = _ingest()

    response = client.post(
        f"/v1/traces/{trace_id}/feedback",
        json={"rating": "thumbs_up", "comment": "Grounded and useful."},
    )
    assert response.status_code == 201
    assert response.json()["rating"] == "thumbs_up"

    feedback = client.get(f"/v1/traces/{trace_id}").json()["feedback"]
    assert len(feedback) == 1
    assert feedback[0]["rating"] == "thumbs_up"
    assert feedback[0]["comment"] == "Grounded and useful."
    assert feedback[0]["created_at"]  # server-stamped


def test_feedback_appends_multiple_entries() -> None:
    trace_id = _ingest()

    client.post(f"/v1/traces/{trace_id}/feedback", json={"rating": "thumbs_up"})
    client.post(f"/v1/traces/{trace_id}/feedback", json={"rating": "thumbs_down"})

    feedback = client.get(f"/v1/traces/{trace_id}").json()["feedback"]
    ratings = [entry["rating"] for entry in feedback]
    assert ratings == ["thumbs_up", "thumbs_down"]


def test_invalid_rating_is_rejected() -> None:
    trace_id = _ingest()

    response = client.post(
        f"/v1/traces/{trace_id}/feedback", json={"rating": "meh"}
    )
    assert response.status_code == 422


def test_feedback_on_missing_trace_returns_404() -> None:
    response = client.post(
        f"/v1/traces/{uuid4()}/feedback", json={"rating": "thumbs_up"}
    )
    assert response.status_code == 404
