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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.claims_agent import ClaimsAgentDeps
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    ClaimQueries,
    GetAseguradoDetailTool,
    GetClaimDetailTool,
    GetProviderDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.core.config import Settings, settings
from app.core.errors import Unauthorized
from app.core.lifespan_state import AIState
from app.domain.anomaly import AnomalyDetector
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.ml import FraudClassifier
from app.domain.similarity import NarrativeSimilarity
from app.infrastructure.audit import AuditStore, DbAuditStore, InMemoryAuditStore
from app.infrastructure.auth import EnvSeededUserRepo, JwtIssuer
from app.infrastructure.db.db_claim_queries import DbClaimQueries
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
from app.infrastructure.reviews.db_reviews_store import DbReviewsStore
from app.infrastructure.reviews.ports import ReviewsStore
from app.infrastructure.rule_changes import InMemoryRuleChangesStore
from app.infrastructure.speech import (
    InMemoryFakeTranscriber,
    SpeechTranscriber,
    build_openai_whisper_adapter,
)
from app.infrastructure.storage import InMemoryStorage, Storage, SupabaseStorage
from app.infrastructure.vectorstore import VectorStore
from app.use_cases.ask_agent import AskAgent
from app.use_cases.auth.login import LoginUseCase
from app.use_cases.conversations.conversation_persister import ConversationPersister
from app.use_cases.conversations.generate_conversation_title import (
    GenerateConversationTitle,
)


def get_settings() -> Settings:
    return settings


# DB session: use ``app.infrastructure.db.engine.get_session`` for required sessions
# and ``_get_optional_session`` below for graceful-degradation paths.

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
    """Dependency factory that enforces a specific role."""

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


def require_any_role(*roles: Role) -> Callable[[User], User]:
    """Dependency factory that accepts one of several roles."""

    def _checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            allowed = ", ".join(role.value for role in roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "role_required",
                    "message": f"Requires one of: {allowed}",
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


def get_speech_transcriber() -> SpeechTranscriber:
    return _fallback_speech_transcriber()


@lru_cache(maxsize=1)
def _fallback_speech_transcriber() -> SpeechTranscriber:
    if settings.LLM_PROVIDER == "fake" or settings.OPENAI_API_KEY is None:
        return InMemoryFakeTranscriber()
    return build_openai_whisper_adapter()


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


def get_fraud_classifier(request: Request) -> FraudClassifier | None:
    """Lifespan-pinned LightGBM classifier; None when the artifact is absent.

    Callers must accept None gracefully — ``enrich_claim_score`` does.
    """
    state = _ai_state(request)
    return state.fraud_classifier if state is not None else None


def get_anomaly_detector(request: Request) -> AnomalyDetector | None:
    """Lifespan-pinned IsolationForest detector; None when the artifact is absent."""
    state = _ai_state(request)
    return state.anomaly_detector if state is not None else None


def get_narrative_similarity(request: Request) -> NarrativeSimilarity | None:
    """Lifespan-pinned NarrativeSimilarity port; None when embeddings are absent.

    The lifespan only sets ``state.similarity`` once embeddings load successfully
    (see ``main._build_similarity``). Callers (re-analysis, FS-13) must accept
    None gracefully — narrative signals are skipped when unavailable.
    """
    state = _ai_state(request)
    return state.similarity if state is not None else None


def get_vector_store() -> VectorStore:
    raise NotImplementedError("VectorStore adapter not yet wired (see vectorstore.* for impls)")


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    """Return SupabaseStorage when SUPABASE_URL is configured, else InMemoryStorage.

    The app boots and all existing endpoints work with Supabase unset (OPTIONAL).
    Re-added per user request — overrides §11/§13 deferral.
    """
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        return SupabaseStorage(
            url=settings.SUPABASE_URL,
            service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
        )
    return InMemoryStorage()


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


async def _get_optional_session() -> AsyncIterator[AsyncSession | None]:
    """Yield an AsyncSession when the factory is initialised, else yield None.

    Kept around for routers that historically tolerated a missing DB; the
    primary claim-queries path now requires a session and raises if it's
    absent.
    """
    from app.infrastructure.db.engine import _session_factory as _sf

    if _sf is None:
        yield None
        return
    async with _sf() as session:
        yield session


async def get_optional_db_session() -> AsyncIterator[AsyncSession | None]:
    """Public alias of _get_optional_session — for routes that degrade gracefully."""
    async for session in _get_optional_session():
        yield session


async def get_claim_queries_dep(
    user: Annotated[User, Depends(get_current_user)],
    _session: Annotated[AsyncSession | None, Depends(_get_optional_session)] = None,
) -> ClaimQueries:
    """Return the active ClaimQueries implementation.

    Database-only — the in-memory `SyntheticClaimQueries` path was retired
    once the DB became the source of truth.
    """
    if _session is None:
        raise RuntimeError(
            "Claim queries require a DB session, but the session factory is not "
            "initialised. Ensure the lifespan has run (set_session_factory called) "
            "before serving requests."
        )
    workspace_id = user.id if settings.AUTH_ENABLED else None
    return DbClaimQueries(_session, workspace_id=workspace_id)


# ---------------------------------------------------------------------------
# Reviews store (Postgres-backed, request-scoped)
# ---------------------------------------------------------------------------

async def get_reviews_store(
    _session: Annotated[AsyncSession | None, Depends(_get_optional_session)] = None,
) -> ReviewsStore:
    """Return a request-scoped ``DbReviewsStore`` backed by the active session.

    Postgres is the source of truth — there is no in-memory fallback in
    production. Tests that need an in-memory store override this dependency
    explicitly with ``app.dependency_overrides[get_reviews_store]``.
    """
    if _session is None:
        raise RuntimeError(
            "Reviews store requires a DB session, but the session factory is "
            "not initialised. Ensure the lifespan has run before serving "
            "requests."
        )
    return DbReviewsStore(_session)


def get_audit_store() -> AuditStore:
    """Return the DB-backed audit store, or an in-memory fallback when no DB.

    Audit events must survive restarts / ``--reload``, so they persist to the
    ``audit_events`` table via ``DbAuditStore`` (its own short transaction per
    write, decoupled from the request/SSE session). Only when no session factory
    is registered (no-DB test / script mode) do we fall back to a process-local
    in-memory log.
    """
    factory = _get_session_factory()
    if factory is None:
        return _fallback_audit_store()
    return DbAuditStore(factory)


@lru_cache(maxsize=1)
def _fallback_audit_store() -> InMemoryAuditStore:
    return InMemoryAuditStore()


@lru_cache(maxsize=1)
def get_rule_changes_store() -> InMemoryRuleChangesStore:
    """Return the process-singleton in-memory rule-change log.

    Starts empty — entries are appended when a rule edit endpoint lands
    post-hackathon. Until then ``GET /rules/changes`` honestly returns ``[]``.
    """
    return InMemoryRuleChangesStore()


def _get_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Return the lifespan-registered async_sessionmaker.

    Raises if the lifespan never ran (test/script paths that bypass it must wire
    a factory in directly; the AskAgent will simply skip persistence in that case).
    """
    from app.infrastructure.db.engine import _session_factory

    return _session_factory


def get_title_generator(
    llm: Annotated[LLMProvider, Depends(get_llm)],
    prompts: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> GenerateConversationTitle:
    return GenerateConversationTitle(
        llm=llm, prompts=prompts, model=settings.LLM_DEFAULT_MODEL
    )


def get_conversation_persister(
    title_gen: Annotated[GenerateConversationTitle, Depends(get_title_generator)],
) -> ConversationPersister | None:
    factory = _get_session_factory()
    if factory is None:
        return None
    return ConversationPersister(session_factory=factory, title_generator=title_gen)


async def get_ask_agent(
    llm: Annotated[LLMProvider, Depends(get_llm)],
    prompts: Annotated[PromptLoader, Depends(get_prompt_loader)],
    queries: Annotated[ClaimQueries, Depends(get_claim_queries_dep)],
    persistence: Annotated[
        ConversationPersister | None, Depends(get_conversation_persister)
    ] = None,
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
        get_provider_detail=GetProviderDetailTool(queries),
        get_asegurado_detail=GetAseguradoDetailTool(queries),
        max_react_steps=settings.MAX_REACT_STEPS,
    )
    return AskAgent(deps=deps, persistence=persistence)
