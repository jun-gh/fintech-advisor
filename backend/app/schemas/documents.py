"""Pydantic v2 schemas for SOP document ingestion and chunk inspection."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    """Payload to ingest or update a compliance SOP document."""

    source_id: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="Stable lowercase slug identifier, e.g. 'sop-reg-e-unauthorized-eft'.",
    )
    title: str = Field(min_length=3, max_length=255)
    version: str = Field(default="1.0", min_length=1, max_length=32)
    category: str = Field(min_length=2, max_length=64)
    content: str = Field(min_length=20, description="Full Markdown or plain-text policy body.")
    metadata: dict[str, Any] = Field(default_factory=dict)
    force: bool = Field(
        default=False,
        description="Re-chunk and re-embed even if the document content hash is unchanged.",
    )


class DocumentIngestResponse(BaseModel):
    """Result of an idempotent SOP ingestion operation."""

    document_id: UUID
    source_id: str
    status: Literal["ingested", "updated", "skipped_unchanged"]
    chunk_count: int
    content_hash: str


class PolicyDocumentSummary(BaseModel):
    """Summary view of an ingested policy document."""

    id: UUID
    source_id: str
    title: str
    version: str
    category: str
    content_hash: str
    chunk_count: int
    updated_at: datetime


class ContextChunkSummary(BaseModel):
    """Inspectable policy chunk with citation metadata (omits raw vector floats)."""

    id: UUID
    chunk_id: str
    chunk_index: int
    section_title: str
    content: str
    metadata: dict[str, Any]


class SeedDocumentsResponse(BaseModel):
    """Summary of seeding the bundled initial Card Dispute & Chargeback SOPs."""

    seeded_count: int
    total_chunks: int
    results: list[DocumentIngestResponse]
