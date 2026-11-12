"""Unit and integration tests for SOP chunking, idempotent ingestion, and pgvector storage."""

import hashlib
from collections.abc import AsyncIterator, Sequence

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import close_db, ensure_schema, get_session_factory, init_db
from app.main import create_app
from app.models.compliance import PolicyDocument
from app.services.embeddings import TaskType, get_embedding_provider
from app.services.ingestion import chunk_markdown_sop


class FakeEmbeddingProvider:
    """Deterministic local embedder for testing ingestion without external API calls."""

    def __init__(self, dimensions: int = 768) -> None:
        self._dimensions = dimensions

    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(f"{task_type}:{text}".encode()).digest()
            base = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self._dimensions)]
            vectors.append(base)
        return vectors


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    settings = get_settings()
    engine = init_db(settings)
    await ensure_schema(engine)
    application = create_app(settings)
    application.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider(
        dimensions=settings.embedding_dimensions
    )
    try:
        yield application
    finally:
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(
                delete(PolicyDocument).where(
                    PolicyDocument.source_id.in_(["test-sop-chargeback", "test-sop-seed-tmp"])
                )
            )
            await session.commit()
        application.dependency_overrides.clear()
        await close_db()


def test_chunk_markdown_sop_preserves_section_hierarchy() -> None:
    sample = (
        "# SOP Test: Disputes\n\nIntro paragraph.\n\n"
        "## 1. Filing Window\n\nMust file within 120 calendar days.\n\n"
        "### 1.1 Visa 10.4\n\nCard-absent fraud evidence rules."
    )
    chunks = chunk_markdown_sop(sample, source_id="sop-test")
    assert len(chunks) >= 2
    assert all(c.chunk_id.startswith("sop-test:") for c in chunks)
    assert any("1. Filing Window" in c.section_title for c in chunks)
    assert any("1.1 Visa 10.4" in c.section_title for c in chunks)


async def test_ingest_is_idempotent_and_supports_updates_and_inspection(app: FastAPI) -> None:
    payload = {
        "source_id": "test-sop-chargeback",
        "title": "Test Chargeback SOP",
        "version": "1.0",
        "category": "test_ops",
        "content": (
            "# Test Chargeback SOP\n\n"
            "## 1. SLA\n\nAnalysts must review representment evidence within 5 business days."
        ),
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_create = await client.post("/api/v1/documents/ingest", json=payload)
        assert res_create.status_code == 201
        created = res_create.json()
        assert created["status"] == "ingested"
        assert created["chunk_count"] >= 1

        # Second call with identical content skips re-embedding
        res_skip = await client.post("/api/v1/documents/ingest", json=payload)
        assert res_skip.status_code == 201
        assert res_skip.json()["status"] == "skipped_unchanged"
        assert res_skip.json()["chunk_count"] == created["chunk_count"]

        # Content change triggers clean update
        updated_payload = {
            **payload,
            "version": "1.1",
            "content": payload["content"] + "\n\n## 2. Escalation\n\nEscalate over $500.",
        }
        res_update = await client.post("/api/v1/documents/ingest", json=updated_payload)
        assert res_update.status_code == 201
        assert res_update.json()["status"] == "updated"

        # List documents & inspect chunks
        res_docs = await client.get("/api/v1/documents")
        assert res_docs.status_code == 200
        assert any(d["source_id"] == "test-sop-chargeback" for d in res_docs.json())

        res_chunks = await client.get("/api/v1/documents/test-sop-chargeback/chunks")
        assert res_chunks.status_code == 200
        chunks = res_chunks.json()
        assert len(chunks) == res_update.json()["chunk_count"]
        assert any("2. Escalation" in c["section_title"] for c in chunks)

        # Missing doc returns uniform 404 ErrorEnvelope
        res_missing = await client.get("/api/v1/documents/nonexistent-sop/chunks")
        assert res_missing.status_code == 404
        assert res_missing.json()["error"]["code"] == "NOT_FOUND"


async def test_seed_endpoint_ingests_markdown_sops_idempotently(
    app: FastAPI, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import sop_seeder

    sample_sop = tmp_path / "01_test_seed.md"
    sample_sop.write_text(
        "# SOP-TEST: Seed Verification\n\n"
        "**Document ID:** `test-sop-seed-tmp`\n"
        "**Version:** `1.0`\n"
        "**Category:** `internal_operations`\n\n"
        "## 1. Rule\n\nSeeded compliance SOP content for testing.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sop_seeder, "SOPS_DIR", tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/documents/seed")
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["seeded_count"] == 1
        assert first_body["total_chunks"] >= 1
        assert first_body["results"][0]["status"] == "ingested"

        second = await client.post("/api/v1/documents/seed")
        assert second.status_code == 200
        assert second.json()["results"][0]["status"] == "skipped_unchanged"
