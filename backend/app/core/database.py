"""Async SQLAlchemy engine, session factory, and pgvector health helpers."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings, get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base declarative class for all ORM models."""


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    """Result of a database and pgvector readiness probe."""

    connected: bool
    pgvector_enabled: bool
    pgvector_version: str | None = None
    error: str | None = None


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine_from_settings(settings: Settings) -> AsyncEngine:
    """Build a configured AsyncEngine with connection pooling."""
    return create_async_engine(
        settings.sqlalchemy_database_url,
        connect_args=settings.database_connect_args,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def init_db(settings: Settings | None = None) -> AsyncEngine:
    """Initialize the module-level AsyncEngine and async_sessionmaker."""
    global _engine, _session_factory
    cfg = settings or get_settings()
    _engine = create_engine_from_settings(cfg)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active async_sessionmaker, initializing on first use if needed."""
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    return _session_factory


def get_engine() -> AsyncEngine:
    """Return the active AsyncEngine, initializing on first use if needed."""
    if _engine is None:
        init_db()
    assert _engine is not None
    return _engine


async def ensure_schema(engine: AsyncEngine | None = None) -> None:
    """Ensure pgvector extension and all ORM tables/indexes exist."""
    import app.models  # noqa: F401 - registers ORM models onto Base.metadata

    target_engine = engine or get_engine()
    async with target_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS answer TEXT NOT NULL DEFAULT ''")
        )


async def close_db() -> None:
    """Dispose the database connection pool cleanly."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a scoped AsyncSession."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def check_db_health(session: AsyncSession) -> DatabaseHealth:
    """Verify PostgreSQL connectivity and pgvector extension availability."""
    try:
        await session.execute(text("SELECT 1"))
        result = await session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        version = result.scalar_one_or_none()
        return DatabaseHealth(
            connected=True,
            pgvector_enabled=version is not None,
            pgvector_version=version,
        )
    except (SQLAlchemyError, OSError, TimeoutError) as exc:
        return DatabaseHealth(
            connected=False,
            pgvector_enabled=False,
            error=type(exc).__name__,
        )
