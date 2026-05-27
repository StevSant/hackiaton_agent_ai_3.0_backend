"""FastAPI dependency wiring.

Heavy adapters (sentence-transformer encoder, ML/anomaly models) are pinned to
`app.state.ai` by the lifespan (`app/core/lifespan_state.py`). These getters read
from `Request.app.state.ai` when available, and fall back to lazy construction
when state is unset (unit tests + scripts that bypass the FastAPI lifespan).
"""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request
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
from app.core.lifespan_state import AIState
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


def _ai_state(request: Request) -> AIState | None:
    return getattr(request.app.state, "ai", None)


def get_ai_state(request: Request) -> AIState:
    """Read the lifespan-pinned AI stack. Raises if the lifespan didn't run."""
    state = _ai_state(request)
    if state is None:
        raise RuntimeError("app.state.ai is not initialized — did the lifespan run?")
    return state


def get_llm(request: Request) -> LLMProvider:
    """LLM provider — reads from lifespan state, falls back when state is unset."""
    state = _ai_state(request)
    if state is not None:
        return state.llm
    return _fallback_llm()


@lru_cache(maxsize=1)
def _fallback_llm() -> LLMProvider:
    if settings.LLM_PROVIDER == "fake" or settings.OPENAI_API_KEY is None:
        return InMemoryFakeLLM()
    return build_openai_adapter()


def get_embeddings(request: Request) -> EmbeddingsProvider:
    state = _ai_state(request)
    if state is not None and state.embeddings is not None:
        return state.embeddings
    return _fallback_embeddings()


@lru_cache(maxsize=1)
def _fallback_embeddings() -> EmbeddingsProvider:
    return SentenceTransformersAdapter(model_name=settings.EMBEDDINGS_MODEL)


def get_vector_store() -> VectorStore:
    raise NotImplementedError("VectorStore adapter not yet wired (see vectorstore.* for impls)")


def get_storage() -> Storage:
    raise NotImplementedError("Storage adapter not yet implemented")


def get_prompt_loader(request: Request) -> PromptLoader:
    state = _ai_state(request)
    if state is not None:
        return state.prompts
    return _fallback_prompt_loader()


@lru_cache(maxsize=1)
def _fallback_prompt_loader() -> PromptLoader:
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "agents" / "claims_agent" / "prompts"
    return PromptLoader(base_dir=base)


def _seed_claims() -> list[ClaimDetail]:
    # In-memory ClaimQueries fallback until V1 dataset lands.
    from tests.fixtures.claims import ALL_FIXTURES  # type: ignore[attr-defined]

    return list(ALL_FIXTURES)


@lru_cache(maxsize=1)
def get_claim_queries() -> ClaimQueries:
    """Today: in-memory backed by 3 hand-crafted fixtures.

    Once Miquel's lane lands `ClaimsRepo`, swap to `DbClaimQueries` behind the
    same Protocol — one new adapter file, no callers change.
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
        max_react_steps=settings.MAX_REACT_STEPS,
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
