"""Unit tests for application configuration and database URL sanitization."""

from app.core.config import Settings, sanitize_asyncpg_url


def test_sanitize_asyncpg_url_normalizes_postgres_schemes() -> None:
    url, connect_args = sanitize_asyncpg_url("postgres://user:pass@localhost:5432/fintech")
    assert url == "postgresql+asyncpg://user:pass@localhost:5432/fintech"
    assert connect_args == {}

    url2, connect_args2 = sanitize_asyncpg_url("postgresql://user:pass@localhost:5432/fintech")
    assert url2 == "postgresql+asyncpg://user:pass@localhost:5432/fintech"
    assert connect_args2 == {}


def test_sanitize_asyncpg_url_extracts_neon_ssl_params() -> None:
    raw = (
        "postgresql://user:pass@ep-demo.us-east-2.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require&application_name=fintech"
    )
    url, connect_args = sanitize_asyncpg_url(raw)
    assert url == (
        "postgresql+asyncpg://user:pass@ep-demo.us-east-2.aws.neon.tech/neondb"
        "?application_name=fintech"
    )
    assert connect_args == {"ssl": "require"}


def test_settings_ignores_frontend_vite_vars_and_masks_secret(monkeypatch) -> None:
    monkeypatch.setenv("VITE_API_BASE_URL", "http://localhost:8000/api/v1")
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-gemini-key")

    settings = Settings(_env_file=None)
    assert settings.gemini_api_key.get_secret_value() == "super-secret-gemini-key"
    assert "super-secret-gemini-key" not in repr(settings)
