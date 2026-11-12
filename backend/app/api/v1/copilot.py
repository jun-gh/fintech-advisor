"""Version 1 Compliance Copilot query, SSE streaming, and audit log endpoints."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError, build_error_envelope
from app.schemas.copilot import AuditLogSummary, CopilotQueryRequest, CopilotQueryResponse
from app.services.copilot import ComplianceCopilotService
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.llm import StructuredLLMClient, get_llm_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post(
    "/query",
    response_model=CopilotQueryResponse,
    summary="Ask the Card Dispute & Chargeback Compliance Copilot",
)
async def query_copilot(
    payload: CopilotQueryRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    llm: Annotated[StructuredLLMClient, Depends(get_llm_client)],
) -> CopilotQueryResponse:
    """Run PII masking, hybrid pgvector/FTS retrieval, grounded generation, and audit logging."""
    request_id = getattr(request.state, "request_id", "unknown")
    service = ComplianceCopilotService(db, embedder, llm)
    return await service.ask(payload, request_id=request_id)


@router.post(
    "/query/stream",
    summary="Stream LangGraph compliance workflow stages and final cited response via SSE",
)
async def stream_copilot(
    payload: CopilotQueryRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    llm: Annotated[StructuredLLMClient, Depends(get_llm_client)],
) -> StreamingResponse:
    """Stream Server-Sent Events showing each LangGraph stage before emitting result or error."""
    request_id = getattr(request.state, "request_id", "unknown")
    service = ComplianceCopilotService(db, embedder, llm)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for item in service.stream_ask(payload, request_id=request_id):
                event_name = item["event"]
                data_json = json.dumps(item["data"])
                yield f"event: {event_name}\ndata: {data_json}\n\n"
        except AppError as exc:
            logger.warning(
                "Copilot stream failed [%s] request_id=%s: %s",
                exc.code,
                request_id,
                exc.message,
            )
            envelope = build_error_envelope(
                code=exc.code,
                message=exc.message,
                request_id=request_id,
                details=exc.details,
            )
            yield f"event: error\ndata: {envelope.model_dump_json()}\n\n"
        except Exception as exc:
            logger.exception(
                "Unhandled exception in copilot stream [request_id=%s]",
                request_id,
                exc_info=exc,
            )
            envelope = build_error_envelope(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal error occurred while generating the response.",
                request_id=request_id,
            )
            yield f"event: error\ndata: {envelope.model_dump_json()}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get(
    "/audit",
    response_model=list[AuditLogSummary],
    summary="List recent compliance copilot audit log entries",
)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AuditLogSummary]:
    """Return recent immutable audit entries for compliance inspection."""
    return await ComplianceCopilotService.list_audit_logs(db, limit=limit)
