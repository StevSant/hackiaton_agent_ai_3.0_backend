from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    agent_router,
    antifraude_router,
    audit_router,
    auth_router,
    claims_reviews_router,
    claims_router,
    conversations_router,
    documents_router,
    health_router,
    imports_router,
    insights_router,
    network_router,
    rules_router,
    status_router,
)
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.lifespan_state import build_lifespan_state
from app.core.logging import configure_logging
from app.infrastructure.db.engine import (
    create_engine,
    create_session_factory,
    set_session_factory,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Heavy adapters (sentence-transformers encoder, optional ML/anomaly models)
    # load ONCE here and pin to app.state — not per-request. Per-request DI reads
    # from app.state via `Request.app.state.*` in deps.py.
    state = build_lifespan_state()
    app.state.ai = state
    # DB: register the async session factory (engine is lazy — no connection opens
    # until the first request checks out a session). Powers DbClaimQueries + repos —
    # the database is the sole source of truth for claims.
    db_engine = create_engine()
    session_factory = create_session_factory(db_engine)
    set_session_factory(session_factory)
    app.state.db_engine = db_engine
    # Attach pgvector similarity now that embeddings + session_factory both exist —
    # used by the SSE import endpoint to fire FS-13 (similar narratives).
    if state.embeddings is not None:
        from app.infrastructure.vectorstore.pgvector_narrative_similarity import (
            PgVectorNarrativeSimilarity,
        )
        state.similarity = PgVectorNarrativeSimilarity(state.embeddings, session_factory)
    try:
        yield
    finally:
        # SentenceTransformer holds torch tensors; explicit drop helps in reload mode.
        app.state.ai = None
        await db_engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(agent_router, prefix=settings.API_V1_PREFIX)
    app.include_router(conversations_router, prefix=settings.API_V1_PREFIX)
    app.include_router(status_router, prefix=settings.API_V1_PREFIX)
    # claims_reviews_router must be included BEFORE claims_router because
    # /claims/historico (a fixed path) must not be shadowed by /claims/{id}.
    app.include_router(claims_reviews_router, prefix=settings.API_V1_PREFIX)
    # imports_router must come before claims_router so fixed paths like
    # /claims/import and /claims/import/template are not shadowed by /claims/{id}.
    app.include_router(imports_router, prefix=settings.API_V1_PREFIX)
    app.include_router(claims_router, prefix=settings.API_V1_PREFIX)
    app.include_router(antifraude_router, prefix=settings.API_V1_PREFIX)
    app.include_router(rules_router, prefix=settings.API_V1_PREFIX)
    app.include_router(network_router, prefix=settings.API_V1_PREFIX)
    app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
    app.include_router(insights_router, prefix=settings.API_V1_PREFIX)
    # documents_router mounts UNDER claims prefix — must come after claims_router
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
