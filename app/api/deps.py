from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.errors import Unauthorized
from app.infrastructure.auth import AuthVerifier, User
from app.infrastructure.embeddings import EmbeddingsProvider
from app.infrastructure.llm import LLMProvider
from app.infrastructure.storage import Storage
from app.infrastructure.vectorstore import VectorStore


def get_settings() -> Settings:
    return settings


async def get_db_session() -> AsyncIterator[AsyncSession]:
    # Wired in app lifespan; this stub is replaced when the engine is provisioned.
    raise NotImplementedError("DB session factory not yet wired — see app/main.py lifespan")


def get_auth_verifier() -> AuthVerifier:
    raise NotImplementedError("AuthVerifier adapter not yet implemented")


def get_llm() -> LLMProvider:
    raise NotImplementedError(
        f"LLM adapter for provider={settings.LLM_PROVIDER} not yet implemented"
    )


def get_embeddings() -> EmbeddingsProvider:
    raise NotImplementedError("Embeddings adapter not yet implemented")


def get_vector_store() -> VectorStore:
    raise NotImplementedError("VectorStore adapter not yet implemented")


def get_storage() -> Storage:
    raise NotImplementedError("Storage adapter not yet implemented")


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    verifier: AuthVerifier = Depends(get_auth_verifier),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1]
    return await verifier.verify(token)
