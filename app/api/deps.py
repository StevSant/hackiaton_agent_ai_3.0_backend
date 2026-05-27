"""FastAPI dependency wiring.

Adapters are constructed lazily per-request (or per-app for the heavy ones —
embeddings, ML model, vector store — which the lifespan should pin to `app.state`
and these getters should read from there once Miquel's lane wires up the lifespan).
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claims_agent import ClaimsAgentDeps
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    ClaimQueries,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.core.config import Settings, settings
from app.core.errors import Unauthorized
from app.infrastructure.auth import AuthVerifier, User
from app.infrastructure.embeddings import EmbeddingsProvider, SentenceTransformersAdapter
from app.infrastructure.llm import (
    InMemoryFakeLLM,
    LLMProvider,
    PromptLoader,
    build_openai_adapter,
)
from app.infrastructure.storage import Storage
from app.infrastructure.vectorstore import VectorStore
from app.schemas.claim import ClaimDetail
from app.use_cases.ask_agent import AskAgent
from app.use_cases.claim_queries import InMemoryClaimQueries


def get_settings() -> Settings:
    return settings


async def get_db_session() -> AsyncIterator[AsyncSession]:
    # Wired in app lifespan; this stub is replaced when the engine is provisioned.
    raise NotImplementedError("DB session factory not yet wired — see app/main.py lifespan")


def get_auth_verifier() -> AuthVerifier:
    raise NotImplementedError("AuthVerifier adapter not yet implemented")


@lru_cache(maxsize=1)
def get_llm() -> LLMProvider:
    """LLM provider singleton. `fake` is intended for tests and offline demos."""
    if settings.LLM_PROVIDER == "fake":
        return InMemoryFakeLLM()
    return build_openai_adapter()


@lru_cache(maxsize=1)
def get_embeddings() -> EmbeddingsProvider:
    return SentenceTransformersAdapter(model_name=settings.EMBEDDINGS_MODEL)


def get_vector_store() -> VectorStore:
    raise NotImplementedError("VectorStore adapter not yet wired (see vectorstore.* for impls)")


def get_storage() -> Storage:
    raise NotImplementedError("Storage adapter not yet implemented")


@lru_cache(maxsize=1)
def get_prompt_loader() -> PromptLoader:
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "agents" / "claims_agent" / "prompts"
    return PromptLoader(base_dir=base)


def _seed_claims() -> list[ClaimDetail]:
    # Used by the in-memory ClaimQueries fallback until V1 dataset lands.
    from tests.fixtures.claims import ALL_FIXTURES  # type: ignore[attr-defined]

    return list(ALL_FIXTURES)


@lru_cache(maxsize=1)
def get_claim_queries() -> ClaimQueries:
    """ClaimQueries used by the agent tools.

    Today: in-memory backed by the 3 hand-crafted fixtures (`tests/fixtures/claims.py`).
    Once Miquel's lane lands the SQLAlchemy `ClaimsRepo`, swap to `DbClaimQueries`
    (one new adapter file behind the same Protocol).
    """
    return InMemoryClaimQueries(claims=_seed_claims())


def get_ask_agent(
    llm: Annotated[LLMProvider, Depends(get_llm)],
    prompts: Annotated[PromptLoader, Depends(get_prompt_loader)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries)],
) -> AskAgent:
    deps = ClaimsAgentDeps(
        llm=llm,
        llm_model=settings.LLM_DEFAULT_MODEL,
        prompts=prompts,
        query_claims=QueryClaimsTool(queries),
        get_claim_detail=GetClaimDetailTool(queries),
        aggregate_by_dimension=AggregateByDimensionTool(queries),
        missing_documents=MissingDocumentsTool(queries),
        summarize_critical=SummarizeCriticalTool(queries),
    )
    return AskAgent(deps=deps)


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    verifier: AuthVerifier = Depends(get_auth_verifier),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing or malformed Authorization header")
    token = authorization.split(" ", 1)[1]
    return await verifier.verify(token)
