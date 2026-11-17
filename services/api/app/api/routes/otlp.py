"""OpenTelemetry ingest: POST /otlp/v1/traces.

Point any OTLP/HTTP exporter at the API with OTEL_EXPORTER_OTLP_ENDPOINT set to
http://<api>/otlp (exporters add /v1/traces themselves) and, when keys are
required, OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer <key>". Protobuf and
JSON are both accepted, gzipped or not. See app/otlp/ for what happens next.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTracePartialSuccess,
    ExportTraceServiceResponse,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenancy import rate_limit, write_project
from app.db.session import get_db
from app.otlp.assembly import accept, finish_quiet
from app.otlp.decode import OtlpDecodeError, TooLarge, UnsupportedMediaType, decode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/otlp/v1", tags=["opentelemetry"])

PROTOBUF = "application/x-protobuf"


async def _body(request: Request) -> bytes:
    return await request.body()


@router.post("/traces")
def export_traces(
    request: Request,
    body: bytes = Depends(_body),
    db: Session = Depends(get_db),
    project_id: str | None = Depends(write_project),
    _limit: None = Depends(rate_limit("ingest", "ingest_rate_limit_per_minute")),
) -> Response:
    content_type = request.headers.get("content-type")
    try:
        decoded = decode(
            body,
            content_type=content_type,
            content_encoding=request.headers.get("content-encoding"),
            max_bytes=get_settings().max_request_bytes,
        )
    except UnsupportedMediaType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except TooLarge as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except OtlpDecodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = accept(db, decoded.spans, key_project=project_id)
    rejected = decoded.rejected + result.rejected

    # Runs whose root never arrived would otherwise wait for the worker's sweep,
    # and there's no worker without Redis: finish quiet ones here too.
    try:
        finish_quiet(db, limit=20)
    except Exception:
        logger.exception("Finishing quiet OpenTelemetry runs failed")
        db.rollback()

    message = (
        f"{rejected} span(s) rejected: invalid ids, or a trace that belongs to another project" if rejected else ""
    )
    if (content_type or "").split(";")[0].strip().lower() == PROTOBUF:
        reply = ExportTraceServiceResponse()
        if rejected:
            reply.partial_success.CopyFrom(ExportTracePartialSuccess(rejected_spans=rejected, error_message=message))
        return Response(content=reply.SerializeToString(), media_type=PROTOBUF)
    payload = {"partialSuccess": {"rejectedSpans": rejected, "errorMessage": message}} if rejected else {}
    return Response(content=json.dumps(payload).encode(), media_type="application/json")
