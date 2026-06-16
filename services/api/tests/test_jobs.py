from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_job_stats_shape_without_redis() -> None:
    # conftest forces redis_url=None, so the queue reports disconnected.
    response = client.get("/v1/jobs/stats")

    assert response.status_code == 200
    body = response.json()
    assert body == {"redis_connected": False, "queued": 0}
