from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.models import EvalRunRecord
from app.schemas.eval_runs import EvalRunIngestRequest


class DuplicateEvalRunError(Exception):
    pass


class EvalRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, eval_run: EvalRunIngestRequest) -> EvalRunRecord:
        payload = eval_run.model_dump(mode="json")

        record = EvalRunRecord(
            eval_run_id=eval_run.eval_run_id,
            schema_version=eval_run.schema_version,
            run_type=eval_run.run_type,
            status=eval_run.status,
            project_id=eval_run.project.project_id,
            environment=eval_run.project.environment,
            dataset_id=eval_run.dataset.dataset_id,
            dataset_name=eval_run.dataset.name,
            dataset_version=eval_run.dataset.version,
            pipeline_version=eval_run.pipeline.pipeline_version,
            baseline_pipeline_version=(
                eval_run.baseline_pipeline.pipeline_version
                if eval_run.baseline_pipeline is not None
                else None
            ),
            total_cases=eval_run.summary.total_cases,
            passed_cases=eval_run.summary.passed_cases,
            failed_cases=eval_run.summary.failed_cases,
            payload=payload,
        )

        self.db.add(record)

        try:
            self.db.commit()
            self.db.refresh(record)
        except IntegrityError as error:
            self.db.rollback()
            raise DuplicateEvalRunError(
                f"Eval run {eval_run.eval_run_id} already exists."
            ) from error

        return record

    def list(self) -> list[EvalRunRecord]:
        statement = select(EvalRunRecord).order_by(EvalRunRecord.created_at.desc())
        return list(self.db.scalars(statement).all())

    def get(self, eval_run_id: UUID) -> EvalRunRecord | None:
        return self.db.get(EvalRunRecord, eval_run_id)