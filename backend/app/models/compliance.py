"""SQLAlchemy ORM models for compliance policy documents, vector chunks, and audit logs."""

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.database import Base

EMBEDDING_DIMENSIONS = get_settings().embedding_dimensions


class PolicyDocument(Base):
    """Represents a versioned fintech compliance or SOP document."""

    __tablename__ = "policy_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    chunks: Mapped[list["ContextChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ContextChunk(Base):
    """Chunked policy section with dense pgvector embedding and PostgreSQL FTS vector."""

    __tablename__ = "context_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_context_chunk_source_idx"),
        Index(
            "idx_context_chunks_hnsw_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_context_chunks_fts_gin", "search_vector", postgresql_using="gin"),
        Index("idx_context_chunks_meta_gin", "chunk_metadata", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policy_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(section_title, '') || ' ' || content)",
            persisted=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["PolicyDocument"] = relationship(back_populates="chunks")


class AuditLog(Base):
    """Immutable audit trail for compliance copilot queries, citations, and guardrails."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    sanitized_query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pii_redacted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
