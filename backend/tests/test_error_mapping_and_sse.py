"""Tests for granular GenAI error mapping and structured SSE error envelopes."""

import hashlib
import json
import re
from collections.abc import AsyncIterator, Sequence

import pytest
from fastapi import FastAPI
from google.genai import errors as genai_errors
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import close_db, ensure_schema, get_session_factory, init_db
from app.core.errors import (
    ModelNotFoundError,
    RateLimitExceededError,
    ServiceUnavailableError,
    UpstreamAuthError,
    UpstreamTimeoutError,
    map_genai_error,
)
from app.main import create_app
from app.services.embeddings import TaskType, get_embedding_provider
from app.services.llm import get_llm_client
from app.services.sop_seeder import seed_default_sops


class FakeEmbeddingProvider:
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
            vectors.append(
                [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self._dimensions)]
            )
        return vectors


class FailingLLMClient:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    @property
    def model_name(self) -> str:
        return "gemini-2.5-flash"

    async def generate_structured(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ):
        raise self._exc


def test_map_genai_error_classifies_rate_limit_auth_missing_timeout_and_503() -> None:
    err_429 = map_genai_error(
        genai_errors.ClientError(429, {"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}),
        model="gemini-2.5-flash",
        operation="compliance generation",
    )
    assert isinstance(err_429, RateLimitExceededError)
    assert err_429.status_code == 429
    assert err_429.code == "MODEL_RATE_LIMIT_EXCEEDED"
    assert err_429.details["retryable"] is True

    err_auth = map_genai_error(
        genai_errors.ClientError(403, {"error": {"code": 403, "message": "API key invalid"}}),
        model="gemini-2.5-flash",
        operation="compliance generation",
    )
    assert isinstance(err_auth, UpstreamAuthError)
    assert err_auth.code == "UPSTREAM_AUTH_ERROR"

    err_404 = map_genai_error(
        genai_errors.ClientError(404, {"error": {"code": 404, "message": "Not found"}}),
        model="bad-model",
        operation="compliance generation",
    )
    assert isinstance(err_404, ModelNotFoundError)
    assert err_404.code == "MODEL_NOT_FOUND"

    err_503 = map_genai_error(
        genai_errors.ServerError(503, {"error": {"code": 503, "message": "Overloaded"}}),
        model="gemini-3.8-flash",
        operation="compliance generation",
    )
    assert isinstance(err_503, ServiceUnavailableError)
    assert err_503.code == "SERVICE_UNAVAILABLE"

    err_timeout = map_genai_error(
        TimeoutError("timed out"),
        model="gemini-3.8-flash",
        operation="compliance generation",
    )
    assert isinstance(err_timeout, UpstreamTimeoutError)
    assert err_timeout.code == "UPSTREAM_TIMEOUT"


@pytest.fixture
async def sse_error_app() -> AsyncIterator[FastAPI]:
    settings = get_settings()
    engine = init_db(settings)
    await ensure_schema(engine)
    fake_embedder = FakeEmbeddingProvider(dimensions=settings.embedding_dimensions)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await seed_default_sops(session, fake_embedder)
        await session.commit()

    application = create_app(settings)
    application.dependency_overrides[get_embedding_provider] = lambda: fake_embedder
    try:
        yield application
    finally:
        application.dependency_overrides.clear()
        await close_db()


async def test_sse_stream_emits_structured_error_event_on_rate_limit(
    sse_error_app: FastAPI,
) -> None:
    rate_limit_exc = RateLimitExceededError(
        "Model rate limit or quota exceeded for 'gemini-2.5-flash'.",
        details={"model": "gemini-2.5-flash", "retryable": True},
    )
    sse_error_app.dependency_overrides[get_llm_client] = lambda: FailingLLMClient(rate_limit_exc)

    async with AsyncClient(
        transport=ASGITransport(app=sse_error_app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/v1/copilot/query/stream",
            headers={"X-Request-ID": "req-sse-429"},
            json={"query": "What is the Regulation E provisional credit deadline?"},
        )

    assert res.status_code == 200
    assert "event: error" in res.text
    match = re.search(r"event: error\ndata: (.+)\n", res.text)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["error"]["code"] == "MODEL_RATE_LIMIT_EXCEEDED"
    assert payload["error"]["request_id"] == "req-sse-429"
    assert payload["error"]["details"]["model"] == "gemini-2.5-flash"
    assert payload["error"]["details"]["retryable"] is True


async def test_sse_stream_sanitizes_unexpected_crash_into_error_event(
    sse_error_app: FastAPI,
) -> None:
    sse_error_app.dependency_overrides[get_llm_client] = lambda: FailingLLMClient(
        RuntimeError("secret internal stack detail")
    )

    async with AsyncClient(
        transport=ASGITransport(app=sse_error_app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/v1/copilot/query/stream",
            headers={"X-Request-ID": "req-sse-500"},
            json={"query": "What is the Visa 10.4 filing limit?"},
        )

    assert res.status_code == 200
    match = re.search(r"event: error\ndata: (.+)\n", res.text)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "secret internal" not in payload["error"]["message"]
