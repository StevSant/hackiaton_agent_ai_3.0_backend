"""FastAPI dependency wiring.

Heavy adapters (sentence-transformer encoder, ML/anomaly models) are pinned to
`app.state.ai` by the lifespan (`app/core/lifespan_state.py`). These getters read
from `Request.app.state.ai` when available, and fall back to lazy construction
when state is unset (unit tests + scripts that bypass the FastAPI lifespan).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
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
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.auth import EnvSeededUserRepo, JwtIssuer
from app.infrastructure.embeddings import (
    EmbeddingsProvider,
    SentenceTransformersAdapter,
    build_openai_embeddings_adapter,
)
from app.infrastructure.llm import (
    InMemoryFakeLLM,
    LLMProvider,
    PromptLoader,
    build_openai_adapter,
)
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore
from app.infrastructure.storage import Storage
from app.infrastructure.vectorstore import VectorStore
from app.schemas.claim import ClaimDetail
from app.use_cases.ask_agent import AskAgent
from app.use_cases.auth.login import LoginUseCase
from app.use_cases.generate_dataset.loader import SyntheticClaimQueries


def get_settings() -> Settings:
    return settings


async def get_db_session() -> AsyncIterator[AsyncSession]:
    # Wired in app lifespan; this stub is replaced when the engine is provisioned.
    raise NotImplementedError("DB session factory not yet wired — see app/main.py lifespan")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_user_repo() -> EnvSeededUserRepo:
    """Singleton: parsed + hashed at first call, reused forever."""
    return EnvSeededUserRepo(settings.AUTH_SEED_USERS.get_secret_value())


@lru_cache(maxsize=1)
def get_auth_verifier() -> JwtIssuer:
    """Return the JWT issuer / verifier singleton."""
    return JwtIssuer()


_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX.lstrip('/')}/auth/token",
    auto_error=False,
)


def get_login_use_case() -> LoginUseCase:
    return LoginUseCase(repo=_get_user_repo(), issuer=get_auth_verifier())


_DEV_STUB_USER = User(
    id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@dev.local"),
    email="analista@dev.local",
    role=Role.analista,
    full_name="Dev Stub",
)


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)] = None,
    verifier: Annotated[JwtIssuer, Depends(get_auth_verifier)] = ...,  # type: ignore[assignment]
) -> User:
    """Decode the Bearer token and return the domain User.

    When ``AUTH_ENABLED=false`` the check is bypassed and a stub analista is returned —
    useful for local demo sessions where login is not needed.
    """
    if not settings.AUTH_ENABLED:
        return _DEV_STUB_USER
    if not token:
        raise Unauthorized("Missing or malformed Authorization header")
    return await verifier.verify(token)


def require_role(role: Role) -> Callable[[User], User]:
    """Dependency factory that enforces a specific role.

    Returns a callable that depends on ``get_current_user`` and raises HTTP 403
    when the authenticated user's role does not match *role*.
    Usage::

        @router.post("/claims/{id}/resolve", dependencies=[Depends(require_role(Role.antifraude))])
    """

    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "role_required",
                    "message": f"Requires role: {role}",
                },
            )
        return user

    return _checker


# ---------------------------------------------------------------------------
# LLM / embeddings / vector store / storage  (AI stack — pinned to app.state.ai)
# ---------------------------------------------------------------------------


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
    if settings.EMBEDDINGS_PROVIDER == "openai" and settings.OPENAI_API_KEY is not None:
        return build_openai_embeddings_adapter()
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
    # Fallback: 3 hand-crafted fixtures (used when dataset file is absent).
    from tests.fixtures.claims import ALL_FIXTURES

    return list(ALL_FIXTURES)


@lru_cache(maxsize=1)
def get_claim_queries() -> ClaimQueries:
    """Backed by the committed synthetic dataset (data/synthetic/claims.json).

    Falls back to 3 hand-crafted fixtures when the file is absent.
    Once the SQLAlchemy-backed DbClaimQueries lands, swap to it here —
    one new adapter file, no callers change.
    """
    return SyntheticClaimQueries()


# ---------------------------------------------------------------------------
# Reviews store (in-memory process singleton for V2.6 workflow)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_reviews_store() -> InMemoryReviewsStore:
    """Return the process-singleton in-memory reviews store.

    Seeded with 2 escalado + 1 dictaminado rows at first call.
    """
    return InMemoryReviewsStore(seed=True)


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
