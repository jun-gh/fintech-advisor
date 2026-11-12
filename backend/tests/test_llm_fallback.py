"""Unit tests for GeminiChatClient primary/fallback model handling."""

from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError
from app.services.llm import GeminiChatClient


class _SampleSchema(BaseModel):
    answer: str


class _FakeAsyncModels:
    def __init__(self, handler) -> None:
        self._handler = handler
        self.called_models: list[str] = []

    async def generate_content(self, *, model: str, contents: str, config):
        self.called_models.append(model)
        return await self._handler(model, contents, config)


def _make_settings(*, primary: str = "gemini-3.8-flash", fallback: str | None = "gemini-2.5-flash") -> Settings:
    return Settings(
        _env_file=None,
        gemini_api_key="test-key",
        gemini_chat_model=primary,
        gemini_fallback_chat_model=fallback,
    )


def test_empty_fallback_env_normalizes_to_none(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_FALLBACK_CHAT_MODEL", "   ")
    settings = Settings(_env_file=None)
    assert settings.gemini_fallback_chat_model is None


async def test_gemini_client_uses_primary_when_healthy() -> None:
    async def handler(model: str, _contents: str, _config):
        return SimpleNamespace(text='{"answer": "primary ok"}')

    fake_models = _FakeAsyncModels(handler)
    client = GeminiChatClient(_make_settings())
    client._client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))

    result = await client.generate_structured(
        system_instruction="sys",
        user_prompt="user",
        response_schema=_SampleSchema,
    )
    assert result.answer == "primary ok"
    assert client.last_used_model == "gemini-3.8-flash"
    assert fake_models.called_models == ["gemini-3.8-flash"]


async def test_gemini_client_falls_back_on_503_spike() -> None:
    async def handler(model: str, _contents: str, _config):
        if model == "gemini-3.8-flash":
            raise genai_errors.ServerError(503, {"error": {"code": 503, "message": "high demand"}})
        return SimpleNamespace(text='{"answer": "fallback ok"}')

    fake_models = _FakeAsyncModels(handler)
    client = GeminiChatClient(_make_settings())
    client._client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))

    result = await client.generate_structured(
        system_instruction="sys",
        user_prompt="user",
        response_schema=_SampleSchema,
    )
    assert result.answer == "fallback ok"
    assert client.last_used_model == "gemini-2.5-flash"
    assert fake_models.called_models == ["gemini-3.8-flash", "gemini-2.5-flash"]


async def test_gemini_client_falls_back_on_timeout() -> None:
    async def handler(model: str, _contents: str, _config):
        if model == "gemini-3.8-flash":
            raise TimeoutError("timed out")
        return SimpleNamespace(text='{"answer": "timeout fallback ok"}')

    fake_models = _FakeAsyncModels(handler)
    client = GeminiChatClient(_make_settings(), primary_timeout_seconds=0.5)
    client._client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))

    result = await client.generate_structured(
        system_instruction="sys",
        user_prompt="user",
        response_schema=_SampleSchema,
    )
    assert result.answer == "timeout fallback ok"
    assert client.last_used_model == "gemini-2.5-flash"


async def test_gemini_client_raises_when_no_fallback_configured() -> None:
    async def handler(model: str, _contents: str, _config):
        raise genai_errors.ServerError(503, {"error": {"code": 503, "message": "high demand"}})

    fake_models = _FakeAsyncModels(handler)
    client = GeminiChatClient(_make_settings(fallback=None))
    client._client = SimpleNamespace(aio=SimpleNamespace(models=fake_models))

    with pytest.raises(ServiceUnavailableError):
        await client.generate_structured(
            system_instruction="sys",
            user_prompt="user",
            response_schema=_SampleSchema,
        )
    assert fake_models.called_models == ["gemini-3.8-flash"]
