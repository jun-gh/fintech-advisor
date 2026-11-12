"""Structured LLM client abstraction and Google Gemini implementation with fallback."""

import asyncio
import logging
from typing import Annotated, Protocol, TypeVar

from fastapi import Depends
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ServiceUnavailableError, map_genai_error

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class StructuredLLMClient(Protocol):
    """Protocol for async structured-output LLM providers."""

    @property
    def model_name(self) -> str: ...

    async def generate_structured(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[TModel],
    ) -> TModel:
        """Generate and validate a response matching response_schema."""
        ...


class GeminiChatClient:
    """Google Gemini async client enforcing Pydantic v2 JSON schema outputs and fallback."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = 1,
        primary_timeout_seconds: float = 10.0,
    ) -> None:
        cfg = settings or get_settings()
        api_key = cfg.gemini_api_key.get_secret_value().strip()
        if not api_key or api_key == "your-gemini-api-key-here":
            raise AppError(
                "GEMINI_API_KEY is not configured.",
                code="MISSING_GEMINI_API_KEY",
                status_code=500,
            )
        self._client = genai.Client(api_key=api_key)
        self._model = cfg.gemini_chat_model
        fallback = cfg.gemini_fallback_chat_model
        self._fallback_model = fallback if fallback and fallback != self._model else None
        self._last_used_model = self._model
        self._max_retries = max_retries
        self._primary_timeout_seconds = primary_timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def last_used_model(self) -> str:
        """Return the model name that served the most recent successful generation."""
        return self._last_used_model

    async def _invoke_model(
        self,
        *,
        model: str,
        user_prompt: str,
        config: types.GenerateContentConfig,
        response_schema: type[TModel],
        timeout_seconds: float | None = None,
    ) -> TModel:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                coro = self._client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
                response = (
                    await asyncio.wait_for(coro, timeout=timeout_seconds)
                    if timeout_seconds is not None
                    else await coro
                )
                if not response.text:
                    raise ValueError("Gemini returned an empty response body.")
                return response_schema.model_validate_json(response.text)
            except ValidationError as exc:
                last_error = exc

        raise ServiceUnavailableError(
            "Gemini response failed structured schema validation.",
            details={"reason": type(last_error).__name__ if last_error else "ValidationError"},
        )

    @staticmethod
    def _is_transient_failure(exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        if isinstance(exc, genai_errors.APIError):
            return exc.code in _TRANSIENT_STATUS_CODES
        return False

    async def generate_structured(
        self,
        *,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[TModel],
    ) -> TModel:
        """Invoke Gemini with JSON schema constraints, falling back on transient spikes."""
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        primary_timeout = self._primary_timeout_seconds if self._fallback_model else None

        try:
            result = await self._invoke_model(
                model=self._model,
                user_prompt=user_prompt,
                config=config,
                response_schema=response_schema,
                timeout_seconds=primary_timeout,
            )
            self._last_used_model = self._model
            return result
        except AppError:
            raise
        except Exception as primary_exc:
            if not self._fallback_model or not self._is_transient_failure(primary_exc):
                raise map_genai_error(
                    primary_exc,
                    model=self._model,
                    operation="compliance generation",
                ) from primary_exc

            logger.warning(
                "Primary model %s experienced transient failure (%s); falling back to %s",
                self._model,
                type(primary_exc).__name__,
                self._fallback_model,
            )

        try:
            result = await self._invoke_model(
                model=self._fallback_model,
                user_prompt=user_prompt,
                config=config,
                response_schema=response_schema,
            )
            self._last_used_model = self._fallback_model
            return result
        except AppError:
            raise
        except Exception as fallback_exc:
            raise map_genai_error(
                fallback_exc,
                model=self._fallback_model,
                operation="fallback compliance generation",
            ) from fallback_exc


def get_llm_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> StructuredLLMClient:
    """FastAPI dependency returning the configured Gemini chat client."""
    return GeminiChatClient(settings=settings)
