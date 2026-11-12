"""Application configuration, environment loading, and database URL sanitization."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: <project_root>/backend/app/core/config.py -> parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = PROJECT_ROOT / ".env"

_SSL_REQUIRED_MODES = {"require", "verify-ca", "verify-full"}


def sanitize_asyncpg_url(raw_url: str) -> tuple[str, dict[str, Any]]:
    """Normalize a Postgres DSN for SQLAlchemy + asyncpg and extract SSL connect_args.

    Managed Postgres providers (such as Neon) often emit ``postgres://`` or
    ``postgresql://`` URLs with ``sslmode`` and ``channel_binding`` query params
    that ``asyncpg`` does not accept directly as URL query parameters.
    """
    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]

    parts = urlsplit(url)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)

    connect_args: dict[str, Any] = {}
    filtered_pairs: list[tuple[str, str]] = []
    for key, value in query_pairs:
        lowered = key.lower()
        if lowered == "sslmode":
            if value.lower() in _SSL_REQUIRED_MODES:
                connect_args["ssl"] = value.lower()
            continue
        if lowered == "channel_binding":
            continue
        filtered_pairs.append((key, value))

    sanitized = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(filtered_pairs), parts.fragment)
    )
    # Neon/PgBouncer transaction poolers do not support asyncpg prepared statement caching
    if parts.hostname and "-pooler" in parts.hostname:
        connect_args["statement_cache_size"] = 0
    return sanitized, connect_args


class Settings(BaseSettings):
    """Validated runtime settings loaded from OS env and the single root ``.env``."""

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "FintechDemo"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Database
    database_url: str = "postgresql+asyncpg://fintech:fintech_dev_password@localhost:5432/fintech_demo"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)

    # Google Gemini (backend-only secrets & dynamic model configuration)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_chat_model: str = "gemini-3.6-flash"
    gemini_fallback_chat_model: str | None = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = Field(default=768, ge=128, le=3072)

    @field_validator("gemini_fallback_chat_model", mode="before")
    @classmethod
    def _empty_fallback_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the asyncpg-compatible SQLAlchemy database URL."""
        sanitized, _ = sanitize_asyncpg_url(self.database_url)
        return sanitized

    @property
    def database_connect_args(self) -> dict[str, Any]:
        """Return asyncpg connection keyword arguments derived from the DSN."""
        _, connect_args = sanitize_asyncpg_url(self.database_url)
        return connect_args


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
