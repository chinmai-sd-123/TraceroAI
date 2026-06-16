from fastapi import APIRouter

from app.services.deep_eval_queue import queue_stats

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/stats")
def get_job_stats() -> dict:
    return queue_stats()
