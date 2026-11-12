"""Section-aware SOP chunking and idempotent PostgreSQL/pgvector ingestion."""

import hashlib
from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ContextChunk, PolicyDocument
from app.schemas.documents import (
    ContextChunkSummary,
    DocumentIngestRequest,
    DocumentIngestResponse,
    PolicyDocumentSummary,
)
from app.services.embeddings import EmbeddingProvider

_HEADER_SPLITS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """Intermediate chunk representation prior to embedding and persistence."""

    chunk_index: int
    chunk_id: str
    section_title: str
    content: str
    metadata: dict[str, Any]


def compute_content_hash(content: str) -> str:
    """Return full SHA-256 hex digest of normalized document content."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def chunk_markdown_sop(
    content: str,
    *,
    source_id: str,
    base_metadata: dict[str, Any] | None = None,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> list[ChunkDraft]:
    """Split a Markdown SOP by headings first, then recursively by size while preserving section context."""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADER_SPLITS,
        strip_headers=False,
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    header_docs = header_splitter.split_text(content.strip())
    if not header_docs:
        return []

    sub_docs = text_splitter.split_documents(header_docs)
    drafts: list[ChunkDraft] = []
    shared_meta = dict(base_metadata or {})

    for idx, doc in enumerate(sub_docs):
        cleaned = doc.page_content.strip()
        if not cleaned:
            continue

        headers = [
            doc.metadata[key]
            for key in ("h1", "h2", "h3")
            if key in doc.metadata and str(doc.metadata[key]).strip()
        ]
        section_title = " > ".join(headers) if headers else source_id
        short_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:12]
        chunk_id = f"{source_id}:{idx}:{short_hash}"

        chunk_meta = {
            **shared_meta,
            "source_id": source_id,
            "chunk_index": idx,
            "chunk_id": chunk_id,
            "section_title": section_title,
        }
        drafts.append(
            ChunkDraft(
                chunk_index=idx,
                chunk_id=chunk_id,
                section_title=section_title[:255],
                content=cleaned,
                metadata=chunk_meta,
            )
        )

    return drafts


class IngestionService:
    """Coordinates idempotent SOP chunking, embedding generation, and persistence."""

    def __init__(
        self, session: AsyncSession, embedder: EmbeddingProvider | None = None
    ) -> None:
        self._session = session
        self._embedder = embedder

    async def ingest_document(self, payload: DocumentIngestRequest) -> DocumentIngestResponse:
        """Ingest or update a policy document idempotently."""
        if self._embedder is None:
            raise ValueError("An EmbeddingProvider is required for document ingestion.")
        content_hash = compute_content_hash(payload.content)

        existing = await self._session.scalar(
            select(PolicyDocument).where(PolicyDocument.source_id == payload.source_id)
        )

        if existing and existing.content_hash == content_hash and not payload.force:
            chunk_count = await self._session.scalar(
                select(func.count(ContextChunk.id)).where(
                    ContextChunk.document_id == existing.id
                )
            )
            return DocumentIngestResponse(
                document_id=existing.id,
                source_id=existing.source_id,
                status="skipped_unchanged",
                chunk_count=int(chunk_count or 0),
                content_hash=content_hash,
            )

        base_meta = {
            **payload.metadata,
            "title": payload.title,
            "version": payload.version,
            "category": payload.category,
        }
        drafts = chunk_markdown_sop(
            payload.content,
            source_id=payload.source_id,
            base_metadata=base_meta,
        )
        vectors = await self._embedder.embed_texts(
            [f"{d.section_title}\n\n{d.content}" for d in drafts],
            task_type="RETRIEVAL_DOCUMENT",
        )

        if existing is None:
            doc = PolicyDocument(
                source_id=payload.source_id,
                title=payload.title,
                version=payload.version,
                category=payload.category,
                content_hash=content_hash,
                doc_metadata=base_meta,
            )
            self._session.add(doc)
            await self._session.flush()
            op_status = "ingested"
        else:
            existing.title = payload.title
            existing.version = payload.version
            existing.category = payload.category
            existing.content_hash = content_hash
            existing.doc_metadata = base_meta
            await self._session.execute(
                delete(ContextChunk).where(ContextChunk.document_id == existing.id)
            )
            await self._session.flush()
            doc = existing
            op_status = "updated"

        for draft, vector in zip(drafts, vectors, strict=True):
            self._session.add(
                ContextChunk(
                    document_id=doc.id,
                    source_id=payload.source_id,
                    chunk_index=draft.chunk_index,
                    chunk_id=draft.chunk_id,
                    section_title=draft.section_title,
                    content=draft.content,
                    chunk_metadata=draft.metadata,
                    embedding=vector,
                )
            )

        await self._session.commit()
        return DocumentIngestResponse(
            document_id=doc.id,
            source_id=doc.source_id,
            status=op_status,
            chunk_count=len(drafts),
            content_hash=content_hash,
        )

    async def list_documents(self) -> list[PolicyDocumentSummary]:
        """List all ingested policy documents along with their chunk counts."""
        stmt = (
            select(
                PolicyDocument,
                func.count(ContextChunk.id).label("chunk_count"),
            )
            .outerjoin(ContextChunk, ContextChunk.document_id == PolicyDocument.id)
            .group_by(PolicyDocument.id)
            .order_by(PolicyDocument.source_id.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            PolicyDocumentSummary(
                id=doc.id,
                source_id=doc.source_id,
                title=doc.title,
                version=doc.version,
                category=doc.category,
                content_hash=doc.content_hash,
                chunk_count=int(chunk_count),
                updated_at=doc.updated_at,
            )
            for doc, chunk_count in rows
        ]

    async def list_document_chunks(self, source_id: str) -> list[ContextChunkSummary] | None:
        """Return ordered chunks for a document, or None if the document does not exist."""
        doc_id = await self._session.scalar(
            select(PolicyDocument.id).where(PolicyDocument.source_id == source_id)
        )
        if doc_id is None:
            return None

        stmt = (
            select(ContextChunk)
            .where(ContextChunk.document_id == doc_id)
            .order_by(ContextChunk.chunk_index.asc())
        )
        chunks = (await self._session.scalars(stmt)).all()
        return [
            ContextChunkSummary(
                id=c.id,
                chunk_id=c.chunk_id,
                chunk_index=c.chunk_index,
                section_title=c.section_title,
                content=c.content,
                metadata=c.chunk_metadata,
            )
            for c in chunks
        ]
