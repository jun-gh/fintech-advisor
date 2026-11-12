"""Hybrid retrieval combining pgvector HNSW cosine search and PostgreSQL FTS via RRF."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ContextChunk, PolicyDocument
from app.services.embeddings import EmbeddingProvider

_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*")


def build_or_websearch_query(query: str, *, max_tokens: int = 16) -> str:
    """Convert a natural-language query into an OR-joined websearch query for FTS recall."""
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in _FTS_TOKEN_RE.findall(query):
        lowered = raw.lower()
        if lowered in seen or lowered in {"or", "and", "not"}:
            continue
        seen.add(lowered)
        tokens.append(raw)
        if len(tokens) >= max_tokens:
            break
    return " OR ".join(tokens) if tokens else query


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Ranked policy chunk returned from hybrid search."""

    chunk_id: str
    source_id: str
    document_title: str
    document_version: str
    category: str
    section_title: str
    content: str
    metadata: dict[str, Any]
    dense_score: float | None = None
    sparse_score: float | None = None
    rrf_score: float = 0.0


def reciprocal_rank_fusion(
    dense_results: Sequence[RetrievedChunk],
    sparse_results: Sequence[RetrievedChunk],
    *,
    k: int = 60,
    top_n: int = 6,
) -> list[RetrievedChunk]:
    """Merge dense semantic and sparse keyword rankings with Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    merged: dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(dense_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + (1.0 / (k + rank + 1))
        merged[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(sparse_results):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + (1.0 / (k + rank + 1))
        if chunk.chunk_id in merged:
            existing = merged[chunk.chunk_id]
            merged[chunk.chunk_id] = RetrievedChunk(
                chunk_id=existing.chunk_id,
                source_id=existing.source_id,
                document_title=existing.document_title,
                document_version=existing.document_version,
                category=existing.category,
                section_title=existing.section_title,
                content=existing.content,
                metadata=existing.metadata,
                dense_score=existing.dense_score,
                sparse_score=chunk.sparse_score,
            )
        else:
            merged[chunk.chunk_id] = chunk

    ranked_ids = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_n]
    return [
        RetrievedChunk(
            chunk_id=merged[cid].chunk_id,
            source_id=merged[cid].source_id,
            document_title=merged[cid].document_title,
            document_version=merged[cid].document_version,
            category=merged[cid].category,
            section_title=merged[cid].section_title,
            content=merged[cid].content,
            metadata=merged[cid].metadata,
            dense_score=merged[cid].dense_score,
            sparse_score=merged[cid].sparse_score,
            rrf_score=score,
        )
        for cid, score in ranked_ids
    ]


class HybridRetriever:
    """Executes dense pgvector + sparse PostgreSQL FTS search and fuses results with RRF."""

    def __init__(self, session: AsyncSession, embedder: EmbeddingProvider) -> None:
        self._session = session
        self._embedder = embedder

    async def dense_search(
        self,
        query: str,
        *,
        limit: int = 10,
        category: str | None = None,
        ef_search: int = 40,
    ) -> list[RetrievedChunk]:
        """Run HNSW cosine similarity search via pgvector."""
        vectors = await self._embedder.embed_texts([query], task_type="RETRIEVAL_QUERY")
        query_vector = vectors[0]

        await self._session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))

        distance_expr = ContextChunk.embedding.cosine_distance(query_vector)
        stmt = (
            select(
                ContextChunk,
                PolicyDocument.title,
                PolicyDocument.version,
                PolicyDocument.category,
                (1.0 - distance_expr).label("dense_score"),
            )
            .join(PolicyDocument, ContextChunk.document_id == PolicyDocument.id)
            .order_by(distance_expr.asc())
            .limit(limit)
        )
        if category:
            stmt = stmt.where(PolicyDocument.category == category)

        rows = (await self._session.execute(stmt)).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                document_title=doc_title,
                document_version=doc_version,
                category=doc_category,
                section_title=chunk.section_title,
                content=chunk.content,
                metadata=chunk.chunk_metadata,
                dense_score=float(dense_score),
            )
            for chunk, doc_title, doc_version, doc_category, dense_score in rows
        ]

    async def sparse_search(
        self,
        query: str,
        *,
        limit: int = 10,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        """Run PostgreSQL full-text keyword search over the GIN-indexed search_vector."""
        fts_query_text = build_or_websearch_query(query)
        ts_query = func.websearch_to_tsquery("english", fts_query_text)
        rank_expr = func.ts_rank_cd(ContextChunk.search_vector, ts_query)

        stmt = (
            select(
                ContextChunk,
                PolicyDocument.title,
                PolicyDocument.version,
                PolicyDocument.category,
                rank_expr.label("sparse_score"),
            )
            .join(PolicyDocument, ContextChunk.document_id == PolicyDocument.id)
            .where(ContextChunk.search_vector.op("@@")(ts_query))
            .order_by(rank_expr.desc())
            .limit(limit)
        )
        if category:
            stmt = stmt.where(PolicyDocument.category == category)

        rows = (await self._session.execute(stmt)).all()
        return [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                document_title=doc_title,
                document_version=doc_version,
                category=doc_category,
                section_title=chunk.section_title,
                content=chunk.content,
                metadata=chunk.chunk_metadata,
                sparse_score=float(sparse_score),
            )
            for chunk, doc_title, doc_version, doc_category, sparse_score in rows
        ]

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 6,
        candidate_k: int = 10,
        category: str | None = None,
    ) -> list[RetrievedChunk]:
        """Execute dense + sparse search and combine via Reciprocal Rank Fusion."""
        dense = await self.dense_search(query, limit=candidate_k, category=category)
        sparse = await self.sparse_search(query, limit=candidate_k, category=category)
        return reciprocal_rank_fusion(dense, sparse, top_n=top_n_or_default(top_k))


def top_n_or_default(top_k: int) -> int:
    return max(1, top_k)
