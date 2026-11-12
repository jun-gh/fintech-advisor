"""FastAPI application factory, lifespan hooks, and middleware wiring."""

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.database import (
    check_db_health,
    close_db,
    ensure_schema,
    get_session_factory,
    init_db,
)
from app.core.errors import register_exception_handlers

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        engine = init_db(cfg)
        session_factory = get_session_factory()
        async with session_factory() as session:
            db_health = await check_db_health(session)
        if db_health.connected:
            try:
                await ensure_schema(engine)
                logger.info(
                    "Database connected and schema ensured (pgvector=%s)",
                    db_health.pgvector_version or "enabled",
                )
            except SQLAlchemyError as exc:  # pragma: no cover - defensive startup guard
                logger.warning("Database schema initialization failed at startup: %s", exc)
        else:
            logger.warning(
                "Database readiness check degraded at startup (connected=%s, pgvector=%s, error=%s)",
                db_health.connected,
                db_health.pgvector_enabled,
                db_health.error,
            )
        try:
            yield
        finally:
            await close_db()

    application = FastAPI(
        title=cfg.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(application)
    application.include_router(api_v1_router, prefix=cfg.api_v1_prefix)
    return application


app = create_app()
