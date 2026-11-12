"""Health check response schema."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Readiness probe payload reporting API, PostgreSQL, and pgvector status."""

    status: Literal["ok", "degraded"]
    app_name: str
    environment: str
    database: Literal["connected", "disconnected"]
    pgvector: Literal["enabled", "disabled"]
    pgvector_version: str | None = None
