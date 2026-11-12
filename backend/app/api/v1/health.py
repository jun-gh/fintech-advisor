"""Version 1 health and readiness endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import check_db_health, get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness and readiness probe",
)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse | JSONResponse:
    """Verify API responsiveness, PostgreSQL connectivity, and pgvector extension."""
    db_health = await check_db_health(db)
    is_ready = db_health.connected and db_health.pgvector_enabled

    payload = HealthResponse(
        status="ok" if is_ready else "degraded",
        app_name=settings.app_name,
        environment=settings.app_env,
        database="connected" if db_health.connected else "disconnected",
        pgvector="enabled" if db_health.pgvector_enabled else "disabled",
        pgvector_version=db_health.pgvector_version,
    )
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    return payload
