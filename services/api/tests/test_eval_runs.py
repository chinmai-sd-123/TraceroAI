from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def make_eval_run_payload() -> dict:
    return {
        "run_type": "regression",
        "status": "completed",
        "dataset": {
            "dataset_id": "golden-set-v1",
            "name": "RAG Golden Set",
            "version": "v1",
        },
        "pipeline": {
            "pipeline_version": "rag-pipeline-v0.1.0",
            "retrieval_strategy": "hybrid",
            "model": "gpt-4o-mini",
        },
        "summary": {
            "total_cases": 2,
            "passed_cases": 1,
            "failed_cases": 1,
            "pass_rate": 0.5,
        },
        "cases": [
            {
                "case_id": "case-001",
                "question": "Which regions are supported?",
                "actual_answer": "US and EU regions are supported.",
                "passed": True,
                "scores": {
                    "groundedness": 0.95,
                },
            },
            {
                "case_id": "case-002",
                "question": "What is the refund period?",
                "actual_answer": "Refunds are available within 14 days.",
                "passed": False,
                "failure_label": "unsupported_claim",
                "reason": "The answer is unsupported.",
                "scores": {
                    "groundedness": 0.4,
                },
            },
        ],
    }


def test_create_eval_run_returns_created() -> None:
    response = client.post("/v1/eval-runs", json=make_eval_run_payload())

    assert response.status_code == 201

    body = response.json()
    assert body["status"] == "created"
    assert body["message"] == "Eval run created successfully."
    assert "eval_run_id" in body


def test_inconsistent_summary_returns_422() -> None:
    payload = make_eval_run_payload()
    payload["summary"]["failed_cases"] = 2

    response = client.post("/v1/eval-runs", json=payload)

    assert response.status_code == 422
    assert "passed_cases + failed_cases must equal total_cases" in response.text

def test_duplicate_eval_run_returns_409() -> None:
    payload = make_eval_run_payload()
    payload["eval_run_id"] = "11111111-1111-4111-8111-111111111111"

    first_response = client.post("/v1/eval-runs", json=payload)
    second_response = client.post("/v1/eval-runs", json=payload)

    assert first_response.status_code in {201, 409}
    assert second_response.status_code == 409
    assert "already exists" in second_response.json()["detail"]

def test_created_eval_run_can_be_fetched_by_id() -> None:
    create_response = client.post(
        "/v1/eval-runs",
        json=make_eval_run_payload(),
    )
    eval_run_id = create_response.json()["eval_run_id"]

    response = client.get(f"/v1/eval-runs/{eval_run_id}")

    assert response.status_code == 200

    eval_run = response.json()
    assert eval_run["eval_run_id"] == eval_run_id
    assert eval_run["run_type"] == "regression"
    assert eval_run["dataset"]["dataset_id"] == "golden-set-v1"
    assert eval_run["summary"]["failed_cases"] == 1


def test_list_eval_runs_includes_created_run() -> None:
    create_response = client.post(
        "/v1/eval-runs",
        json=make_eval_run_payload(),
    )
    eval_run_id = create_response.json()["eval_run_id"]

    response = client.get("/v1/eval-runs")

    assert response.status_code == 200

    eval_run_ids = [
        eval_run["eval_run_id"]
        for eval_run in response.json()
    ]

    assert eval_run_id in eval_run_ids


def test_get_missing_eval_run_returns_404() -> None:
    response = client.get(
        "/v1/eval-runs/22222222-2222-4222-8222-222222222222"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Eval run not found.",
    }