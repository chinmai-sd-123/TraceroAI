from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.schemas.traces import ProjectInfo


EvalRunType = Literal["regression", "experiment"]
EvalRunStatus = Literal["queued", "running", "completed", "failed"]


class EvalDataset(BaseModel):
    dataset_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str | None = None


class PipelineConfig(BaseModel):
    pipeline_version: str = Field(..., min_length=1)
    retrieval_strategy: str | None = None
    prompt_version: str | None = None
    model: str | None = None
    embedding_model: str | None = None
    reranker: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class EvalMetricSummary(BaseModel):
    metric_name: str = Field(..., min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    threshold: float | None = Field(default=None, ge=0, le=1)
    passed: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvalCaseResult(BaseModel):
    case_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    expected_answer: str | None = None
    actual_answer: str | None = None

    passed: bool
    failure_label: str | None = None
    reason: str | None = None

    trace_id: UUID | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentVariantResult(BaseModel):
    variant_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)

    passed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    average_latency_ms: int | None = Field(default=None, ge=0)

    metrics: list[EvalMetricSummary] = Field(default_factory=list)


class EvalRunSummary(BaseModel):
    total_cases: int = Field(default=0, ge=0)
    passed_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    pass_rate: float | None = Field(default=None, ge=0, le=1)
    recommendation: str | None = None


class EvalRunIngestRequest(BaseModel):
    schema_version: str = Field(default="tracero_eval_run_v1")
    eval_run_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    run_type: EvalRunType
    status: EvalRunStatus = Field(default="completed")

    project: ProjectInfo = Field(default_factory=ProjectInfo)
    dataset: EvalDataset
    pipeline: PipelineConfig
    baseline_pipeline: PipelineConfig | None = None

    summary: EvalRunSummary = Field(default_factory=EvalRunSummary)
    metrics: list[EvalMetricSummary] = Field(default_factory=list)
    cases: list[EvalCaseResult] = Field(default_factory=list)
    variants: list[ExperimentVariantResult] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)
    @model_validator(mode="after")
    def validate_run_consistency(self) -> "EvalRunIngestRequest":
        summary = self.summary

        if summary.passed_cases + summary.failed_cases != summary.total_cases:
            raise ValueError(
                "passed_cases + failed_cases must equal total_cases"
            )

        if summary.total_cases == 0:
            expected_pass_rate = 0.0
        else:
            expected_pass_rate = summary.passed_cases / summary.total_cases

        if (
            summary.pass_rate is not None
            and abs(summary.pass_rate - expected_pass_rate) > 0.001
        ):
            raise ValueError(
                "pass_rate must equal passed_cases / total_cases"
            )

        if self.status != "completed":
            return self

        if self.run_type == "regression":
            if not self.cases:
                raise ValueError(
                    "completed regression runs must contain cases"
                )

            if self.variants:
                raise ValueError(
                    "regression runs cannot contain experiment variants"
                )

            passed_cases = sum(case.passed for case in self.cases)
            failed_cases = len(self.cases) - passed_cases

            if len(self.cases) != summary.total_cases:
                raise ValueError(
                    "summary total_cases must equal the number of cases"
                )

            if passed_cases != summary.passed_cases:
                raise ValueError(
                    "summary passed_cases does not match case results"
                )

            if failed_cases != summary.failed_cases:
                raise ValueError(
                    "summary failed_cases does not match case results"
                )

        if self.run_type == "experiment":
            if len(self.variants) < 2:
                raise ValueError(
                    "completed experiments must contain at least two variants"
                )

            if self.cases:
                raise ValueError(
                    "experiment cases require variant association and are not supported yet"
                )

        return self


class EvalRunIngestResponse(BaseModel):
    eval_run_id: UUID
    status: str
    message: str