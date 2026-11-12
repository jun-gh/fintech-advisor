"""Centralized error types, response envelopes, upstream error mapping, and FastAPI handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google.genai import errors as genai_errors
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    """Structured error payload returned for all API failures."""

    code: str
    message: str
    request_id: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """Top-level JSON error wrapper."""

    error: ErrorDetail


class AppError(Exception):
    """Base domain/application exception mapped to a consistent HTTP error envelope."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, message: str = "Resource not found", details: Any | None = None) -> None:
        super().__init__(
            message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class RateLimitExceededError(AppError):
    """Raised when an upstream AI provider rate limit or quota is exceeded."""

    def __init__(
        self,
        message: str = "AI model rate limit or quota exceeded. Please wait and retry.",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message,
            code="MODEL_RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class UpstreamTimeoutError(AppError):
    """Raised when an upstream AI or database call times out."""

    def __init__(
        self,
        message: str = "The AI model took too long to respond. Please try again.",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message,
            code="UPSTREAM_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=details,
        )


class UpstreamAuthError(AppError):
    """Raised when upstream AI provider credentials are invalid or rejected."""

    def __init__(
        self,
        message: str = "AI provider authentication failed. Verify GEMINI_API_KEY configuration.",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message,
            code="UPSTREAM_AUTH_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class ModelNotFoundError(AppError):
    """Raised when a configured AI model name does not exist or is unsupported."""

    def __init__(
        self,
        message: str = "Configured AI model was not found or is unsupported.",
        details: Any | None = None,
    ) -> None:
        super().__init__(
            message,
            code="MODEL_NOT_FOUND",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


class ServiceUnavailableError(AppError):
    """Raised when a required downstream dependency (DB, LLM) is unavailable."""

    def __init__(
        self, message: str = "Required service is unavailable", details: Any | None = None
    ) -> None:
        super().__init__(
            message,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


def map_genai_error(exc: Exception, *, model: str, operation: str) -> AppError:
    """Translate Google GenAI SDK / timeout exceptions into safe, descriptive AppErrors."""
    if isinstance(exc, AppError):
        return exc

    if isinstance(exc, TimeoutError):
        return UpstreamTimeoutError(
            f"AI model '{model}' timed out during {operation}. Please retry.",
            details={"model": model, "operation": operation, "retryable": True},
        )

    if isinstance(exc, genai_errors.APIError):
        code = exc.code
        details = {"model": model, "operation": operation, "upstream_status": code}

        if code == 429 or "RESOURCE_EXHAUSTED" in str(exc):
            return RateLimitExceededError(
                f"Model rate limit or quota exceeded for '{model}' during {operation}. "
                "Please wait a moment and try again.",
                details={**details, "retryable": True},
            )
        if code in {401, 403}:
            return UpstreamAuthError(
                "Gemini API rejected authentication credentials. Check GEMINI_API_KEY in .env.",
                details={**details, "retryable": False},
            )
        if code == 404:
            return ModelNotFoundError(
                f"Configured model '{model}' was not found or does not support {operation}.",
                details={**details, "retryable": False},
            )
        if code in {500, 502, 503, 504}:
            return ServiceUnavailableError(
                f"AI model '{model}' is experiencing temporary high demand ({code}). Please retry.",
                details={**details, "retryable": True},
            )
        return AppError(
            f"AI provider returned an error ({code}) for model '{model}'.",
            code="UPSTREAM_API_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={**details, "retryable": False},
        )

    return ServiceUnavailableError(
        f"Failed to complete {operation} with model '{model}'.",
        details={"model": model, "operation": operation, "reason": type(exc).__name__, "retryable": True},
    )


def build_error_envelope(
    *,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
) -> ErrorEnvelope:
    """Create a uniform ErrorEnvelope instance."""
    return ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=request_id,
            details=details,
        )
    )


def _extract_request_id(request: Request) -> str:
    return (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or "unknown"
    )


def _envelope_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Any | None = None,
) -> JSONResponse:
    payload = build_error_envelope(
        code=code,
        message=message,
        request_id=request_id,
        details=details,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers producing uniform ErrorEnvelope responses."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=_extract_request_id(request),
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        sanitized_errors = [
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ]
        return _envelope_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            request_id=_extract_request_id(request),
            details=sanitized_errors,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = _extract_request_id(request)
        logger.exception("Unhandled exception [request_id=%s]", request_id, exc_info=exc)
        return _envelope_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal error occurred.",
            request_id=request_id,
        )
