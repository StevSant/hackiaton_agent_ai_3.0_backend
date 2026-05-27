from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    agent_router,
    antifraude_router,
    auth_router,
    claims_reviews_router,
    claims_router,
    documents_router,
    health_router,
    rules_router,
    status_router,
)
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.lifespan_state import build_lifespan_state
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Heavy adapters (sentence-transformers encoder, optional ML/anomaly models)
    # load ONCE here and pin to app.state — not per-request. Per-request DI reads
    # from app.state via `Request.app.state.*` in deps.py.
    state = build_lifespan_state()
    app.state.ai = state
    try:
        yield
    finally:
        # SentenceTransformer holds torch tensors; explicit drop helps in reload mode.
        app.state.ai = None


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
    app.include_router(status_router, prefix=settings.API_V1_PREFIX)
    # claims_reviews_router must be included BEFORE claims_router because
    # /claims/historico (a fixed path) must not be shadowed by /claims/{id}.
    app.include_router(claims_reviews_router, prefix=settings.API_V1_PREFIX)
    app.include_router(claims_router, prefix=settings.API_V1_PREFIX)
    app.include_router(antifraude_router, prefix=settings.API_V1_PREFIX)
    app.include_router(rules_router, prefix=settings.API_V1_PREFIX)
    # documents_router mounts UNDER claims prefix — must come after claims_router
    app.include_router(documents_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
