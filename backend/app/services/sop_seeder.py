"""Shared loader and idempotent seeder for bundled Card Dispute & Chargeback SOPs."""

import re
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.documents import DocumentIngestRequest, DocumentIngestResponse
from app.services.embeddings import EmbeddingProvider
from app.services.ingestion import IngestionService

# <backend>/app/services/sop_seeder.py -> parents[2] == <backend>
SOPS_DIR = Path(__file__).resolve().parents[2] / "data" / "sops"

_HEADER_PATTERNS = {
    "source_id": re.compile(r"\*\*Document ID:\*\*\s*`([^`]+)`"),
    "version": re.compile(r"\*\*Version:\*\*\s*`([^`]+)`"),
    "category": re.compile(r"\*\*Category:\*\*\s*`([^`]+)`"),
    "owner": re.compile(r"\*\*Owner:\*\*\s*(.+)"),
}


def parse_sop_markdown(path: Path) -> DocumentIngestRequest:
    """Extract SOP metadata headers and content from a Markdown file."""
    content = path.read_text(encoding="utf-8")
    first_heading = next(
        (line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("# ")),
        path.stem,
    )

    extracted: dict[str, str] = {}
    for key, pattern in _HEADER_PATTERNS.items():
        match = pattern.search(content)
        if match:
            extracted[key] = match.group(1).strip()

    return DocumentIngestRequest(
        source_id=extracted.get("source_id", path.stem),
        title=first_heading,
        version=extracted.get("version", "1.0"),
        category=extracted.get("category", "compliance"),
        content=content,
        metadata={
            "filename": path.name,
            "owner": extracted.get("owner", "Dispute Compliance"),
        },
    )


async def seed_default_sops(
    session: AsyncSession,
    embedder: EmbeddingProvider,
    *,
    sops_dir: Path | None = None,
) -> list[DocumentIngestResponse]:
    """Ingest all bundled Markdown SOP files idempotently into PostgreSQL/pgvector."""
    target_dir = sops_dir or SOPS_DIR
    service = IngestionService(session, embedder)
    results: list[DocumentIngestResponse] = []
    for sop_path in sorted(target_dir.glob("*.md")):
        payload = parse_sop_markdown(sop_path)
        results.append(await service.ingest_document(payload))
    return results
