from datetime import datetime, UTC
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

class ProjectInfo(BaseModel):
    project_id: str= Field(default="demo-rag", min_length=1)
    environment: str= Field(default="dev", min_length=1)

class QueryTrace(BaseModel):
    original: str= Field(..., min_length=1)
    rewritten: str | None = None
    rewrite_changed: bool = False
    rewrite_method: str | None = None
    rewrite_version: str | None = None

class RetrievalConfig(BaseModel):
    lexical_top_k: int | None = None
    dense_top_k: int | None = None
    final_top_k: int | None = None
    fusion: str | None = None
    reranker: str | None = None

class RetrievedChunk(BaseModel):
    rank: int = Field(..., ge=1)
    chunk_id: str = Field(..., min_length=1)
    document_id: str | None = None
    document_title: str | None = None
    section: str | None = None
    source: str | None = None

    base_score: float | None = None
    final_score: float | None = None
    rrf_score: float | None = None
    lexical_rank: int | None = None
    dense_rank: int | None = None
    lexical_score: float | None = None
    dense_score: float | None = None

    text: str = Field(..., min_length=1)
    text_preview: str | None = None

class RetrievalTrace(BaseModel):
    strategy: str = Field(default="vector", min_length=1)
    config: RetrievalConfig = Field(default_factory=RetrievalConfig)
    chunks: list[RetrievedChunk] = Field(default_factory=list)


class PromptTrace(BaseModel):
    version: str | None = None
    template_name: str | None= None
    content: str | None = None

class GenerationTrace(BaseModel):
    provider: str | None= None
    model: str= Field(..., min_length=1)
    temperature: float | None= None
    answer: str= Field(..., min_length=1)
    answered: bool= True

class LatencyTrace(BaseModel):
    retrieval_ms: int | None= Field(default=None, ge=0)
    prompt_build_ms: int | None= Field(default=None, ge=0)
    generation_ms: int | None= Field(default=None, ge=0)
    total_ms:int | None= Field(default=None, ge=0)

class DiagnosisTrace(BaseModel):
    label: str= Field(default= "pending", min_length=1)
    reason:str | None= None

class EvaluationResult(BaseModel):
    evaluator_name: str
    evaluator_version: str | None = None
    label: str
    score: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

class EvaluationsTrace(BaseModel):
    quick: list[EvaluationResult] = Field(default_factory=list)
    deep: list[EvaluationResult] = Field(default_factory=list)

class TraceIngestRequest(BaseModel):
    schema_version: str = Field(default="tracero_trace_v1")
    trace_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = Field(default="answered")

    project: ProjectInfo = Field(default_factory=ProjectInfo)
    query: QueryTrace
    retrieval: RetrievalTrace
    prompt: PromptTrace = Field(default_factory=PromptTrace)
    generation: GenerationTrace
    latency: LatencyTrace = Field(default_factory=LatencyTrace)
    evaluations: EvaluationsTrace = Field(default_factory=EvaluationsTrace)
    diagnosis: DiagnosisTrace = Field(default_factory=DiagnosisTrace)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceIngestResponse(BaseModel):
    trace_id: UUID
    status: str
    message: str
