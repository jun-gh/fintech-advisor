"""Embedding provider abstraction and Google Gemini implementation."""

import asyncio
from collections.abc import Sequence
from typing import Annotated, Literal, Protocol

from fastapi import Depends
from google import genai
from google.genai import types

from app.core.config import Settings, get_settings
from app.core.errors import AppError, ServiceUnavailableError, map_genai_error

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


class EmbeddingProvider(Protocol):
    """Protocol for async text embedding providers."""

    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Generate vector embeddings for a batch of input texts."""
        ...


class GeminiEmbeddingProvider:
    """Async embedding provider backed by the Google GenAI SDK."""

    def __init__(self, settings: Settings | None = None, *, max_concurrency: int = 5) -> None:
        cfg = settings or get_settings()
        api_key = cfg.gemini_api_key.get_secret_value().strip()
        if not api_key or api_key == "your-gemini-api-key-here":
            raise AppError(
                "GEMINI_API_KEY is not configured.",
                code="MISSING_GEMINI_API_KEY",
                status_code=500,
            )
        self._client = genai.Client(api_key=api_key)
        self._model = cfg.gemini_embedding_model
        self._dimensions = cfg.embedding_dimensions
        self._max_concurrency = max_concurrency

    async def _embed_single(
        self,
        text: str,
        config: types.EmbedContentConfig,
        semaphore: asyncio.Semaphore,
    ) -> list[float]:
        async with semaphore:
            response = await self._client.aio.models.embed_content(
                model=self._model,
                contents=text,
                config=config,
            )
        if not response.embeddings or response.embeddings[0].values is None:
            raise ServiceUnavailableError("Gemini returned an empty embedding vector.")
        return list(response.embeddings[0].values)

    async def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: TaskType = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Embed texts concurrently with bounded parallelism while preserving input order."""
        if not texts:
            return []

        config = types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=self._dimensions,
        )
        semaphore = asyncio.Semaphore(self._max_concurrency)

        try:
            vectors = await asyncio.gather(
                *(self._embed_single(text, config, semaphore) for text in texts)
            )
            return list(vectors)
        except AppError:
            raise
        except Exception as exc:
            raise map_genai_error(
                exc,
                model=self._model,
                operation="embedding generation",
            ) from exc


def get_embedding_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingProvider:
    """FastAPI dependency returning the configured embedding provider."""
    return GeminiEmbeddingProvider(settings=settings)
