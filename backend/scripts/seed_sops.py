"""Bootstrap schema and ingest sample Card Dispute & Chargeback SOPs into pgvector."""

import asyncio

from app.core.config import get_settings
from app.core.database import close_db, ensure_schema, get_session_factory, init_db
from app.services.embeddings import GeminiEmbeddingProvider
from app.services.sop_seeder import SOPS_DIR, parse_sop_markdown, seed_default_sops

__all__ = ["SOPS_DIR", "parse_sop_markdown", "seed_all"]


async def seed_all() -> None:
    """Ensure DB schema exists and ingest all Markdown SOP files."""
    settings = get_settings()
    engine = init_db(settings)
    await ensure_schema(engine)

    embedder = GeminiEmbeddingProvider(settings)
    session_factory = get_session_factory()

    try:
        async with session_factory() as session:
            results = await seed_default_sops(session, embedder)
            for result in results:
                print(
                    f"[{result.status}] {result.source_id} "
                    f"({result.chunk_count} chunks, hash={result.content_hash[:10]})"
                )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(seed_all())
