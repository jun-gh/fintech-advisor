"""Version 1 endpoints for SOP document ingestion and chunk inspection."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.schemas.documents import (
    ContextChunkSummary,
    DocumentIngestRequest,
    DocumentIngestResponse,
    PolicyDocumentSummary,
    SeedDocumentsResponse,
)
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.ingestion import IngestionService
from app.services.sop_seeder import seed_default_sops

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/ingest",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest or update a compliance SOP document",
)
async def ingest_document(
    payload: DocumentIngestRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> DocumentIngestResponse:
    """Chunk, embed with Gemini, and store a policy SOP idempotently in pgvector."""
    service = IngestionService(db, embedder)
    return await service.ingest_document(payload)


@router.post(
    "/seed",
    response_model=SeedDocumentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Seed bundled initial Card Dispute & Chargeback SOPs",
)
async def seed_initial_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> SeedDocumentsResponse:
    """Idempotently chunk, embed, and store the bundled initial SOP corpus in pgvector."""
    results = await seed_default_sops(db, embedder)
    return SeedDocumentsResponse(
        seeded_count=len(results),
        total_chunks=sum(item.chunk_count for item in results),
        results=results,
    )


@router.get(
    "",
    response_model=list[PolicyDocumentSummary],
    summary="List ingested compliance policy documents",
)
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PolicyDocumentSummary]:
    """Return metadata and chunk counts for all stored policy documents."""
    service = IngestionService(db)
    return await service.list_documents()


@router.get(
    "/{source_id}/chunks",
    response_model=list[ContextChunkSummary],
    summary="Inspect stored chunks for a policy document",
)
async def list_document_chunks(
    source_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ContextChunkSummary]:
    """Return ordered chunks and section metadata for citation verification."""
    service = IngestionService(db)
    chunks = await service.list_document_chunks(source_id)
    if chunks is None:
        raise NotFoundError(
            f"Policy document '{source_id}' was not found.",
            details={"source_id": source_id},
        )
    return chunks
