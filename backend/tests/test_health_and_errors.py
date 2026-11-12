"""Integration and unit tests for /api/v1/health and centralized error envelopes."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.v1 import health as health_module
from app.core.config import get_settings
from app.core.database import DatabaseHealth, close_db, init_db
from app.core.errors import NotFoundError
from app.main import create_app


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    settings = get_settings()
    init_db(settings)
    application = create_app(settings)
    try:
        yield application
    finally:
        await close_db()


async def test_health_endpoint_reports_connected_pgvector(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": "req-health-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-health-1"
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == get_settings().app_name
    assert body["database"] == "connected"
    assert body["pgvector"] == "enabled"
    assert body["pgvector_version"] is not None


async def test_health_endpoint_returns_503_when_db_unavailable(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_check(_session):
        return DatabaseHealth(connected=False, pgvector_enabled=False, error="ConnectionRefusedError")

    monkeypatch.setattr(health_module, "check_db_health", fake_check)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "disconnected"
    assert body["pgvector"] == "disabled"


async def test_error_envelopes_for_app_validation_and_unexpected_errors(app: FastAPI) -> None:
    class SampleBody(BaseModel):
        amount: int

    @app.get("/_test/not-found")
    async def trigger_not_found() -> None:
        raise NotFoundError("Policy document missing", details={"doc_id": "sop-999"})

    @app.post("/_test/validate")
    async def trigger_validation(payload: SampleBody) -> dict[str, int]:
        return {"amount": payload.amount}

    @app.get("/_test/crash")
    async def trigger_crash() -> None:
        raise RuntimeError("sensitive internal connection string leak")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        not_found_res = await client.get("/_test/not-found", headers={"X-Request-ID": "req-404"})
        val_res = await client.post("/_test/validate", json={"amount": "not-an-int"})
        crash_res = await client.get("/_test/crash", headers={"X-Request-ID": "req-500"})

    assert not_found_res.status_code == 404
    assert not_found_res.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Policy document missing",
            "request_id": "req-404",
            "details": {"doc_id": "sop-999"},
        }
    }

    assert val_res.status_code == 422
    val_body = val_res.json()
    assert val_body["error"]["code"] == "VALIDATION_ERROR"
    assert val_body["error"]["request_id"]
    assert isinstance(val_body["error"]["details"], list)

    assert crash_res.status_code == 500
    crash_body = crash_res.json()
    assert crash_body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert crash_body["error"]["request_id"] == "req-500"
    assert "sensitive internal" not in crash_body["error"]["message"]
