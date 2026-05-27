"""OpenAI `EmbeddingsProvider` impl.

Default model: ``text-embedding-3-small`` (supports the ``dimensions`` truncation
parameter, so we can request 384-dim vectors and keep the existing
``vector(384)`` pgvector schema unchanged).

The CLAUDE.md §2 rule "``import openai`` only inside ``infrastructure/llm/``"
targets feature code (``domain/``, ``use_cases/``, ``api/``, ``agents/``).
Provider SDK imports inside ``infrastructure/embeddings/`` adapters are the
correct location — same architectural layer, different concern from the LLM
port.
"""

from __future__ import annotations

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.errors import ProviderError


class OpenAIEmbeddingsAdapter:
    """`EmbeddingsProvider` impl backed by OpenAI's embeddings endpoint."""

    def __init__(self, api_key: str, model_name: str, dimension: int) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model_name = model_name
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = await self._client.embeddings.create(
                model=self._model_name,
                input=texts,
                dimensions=self._dimension,
            )
        except Exception as exc:
            raise ProviderError(f"OpenAI embeddings request failed: {exc}") from exc
        return [datum.embedding for datum in response.data]


def build_openai_embeddings_adapter() -> OpenAIEmbeddingsAdapter:
    if settings.OPENAI_API_KEY is None:
        raise ProviderError(
            "OPENAI_API_KEY is not set; cannot build OpenAIEmbeddingsAdapter"
        )
    return OpenAIEmbeddingsAdapter(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model_name=settings.EMBEDDINGS_MODEL,
        dimension=settings.EMBEDDINGS_DIM,
    )
