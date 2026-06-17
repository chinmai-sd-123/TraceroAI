from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.eval_runs import EvalRunIngestRequest, EvalRunIngestResponse
from app.services.eval_run_repository import EvalRunRepository, DuplicateEvalRunError


router = APIRouter(prefix="/v1/eval-runs", tags=["eval-runs"])


@router.post(
    "",
    response_model=EvalRunIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_eval_run(
    payload: EvalRunIngestRequest,
    db: Session = Depends(get_db),
) -> EvalRunIngestResponse:
    repository = EvalRunRepository(db)
    try:
        repository.save(payload)
    except DuplicateEvalRunError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return EvalRunIngestResponse(
        eval_run_id=payload.eval_run_id,
        status="created",
        message="Eval run created successfully.",
    )


@router.get("", response_model=list[EvalRunIngestRequest])
def list_eval_runs(
    project_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    repository = EvalRunRepository(db)
    records = repository.list(project_id=project_id)

    return [record.payload for record in records]


# Declared before /{eval_run_id} so "projects" isn't captured as an id.
@router.get("/projects", response_model=list[str])
def list_eval_run_projects(db: Session = Depends(get_db)) -> list[str]:
    repository = EvalRunRepository(db)
    return repository.list_projects()


@router.get("/{eval_run_id}", response_model=EvalRunIngestRequest)
def get_eval_run(
    eval_run_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    repository = EvalRunRepository(db)
    record = repository.get(eval_run_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Eval run not found.",
        )

    return record.payload