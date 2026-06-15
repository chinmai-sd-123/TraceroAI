from datetime import datetime
from uuid import UUID as PythonUUID

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class TraceRecord(Base):
    __tablename__ = "traces"

    trace_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    query_text: Mapped[str] = mapped_column(String, nullable=False)
    diagnosis_label: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_latency_ms: Mapped[int|None] = mapped_column(Integer, nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False,)