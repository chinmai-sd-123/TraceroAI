from uuid import UUID

from app.schemas.traces import TraceIngestRequest


class InMemoryTraceStore:
    def __init__(self) -> None:
        self._traces: dict[UUID, TraceIngestRequest] = {}

    def save(self, trace: TraceIngestRequest) -> TraceIngestRequest:
        self._traces[trace.trace_id] = trace
        return trace

    def list(self) -> list[TraceIngestRequest]:
        return list(self._traces.values())

    def get(self, trace_id: UUID) -> TraceIngestRequest | None:
        return self._traces.get(trace_id)


trace_store = InMemoryTraceStore()