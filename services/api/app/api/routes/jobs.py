from fastapi import APIRouter, Depends

from app.core.tenancy import read_scope
from app.services.deep_eval_queue import queue_stats

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


# Queue depth covers every project, but it's counts only, so anyone who may read
# some project may see it.
@router.get("/stats", dependencies=[Depends(read_scope)])
def get_job_stats() -> dict:
    return queue_stats()
