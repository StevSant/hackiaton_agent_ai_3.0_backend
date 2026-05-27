from app.api.v1.agent import router as agent_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import auth_router
from app.api.v1.claims import router as claims_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.imports import router as imports_router
from app.api.v1.insights import router as insights_router
from app.api.v1.network import router as network_router
from app.api.v1.reviews import antifraude_router, claims_reviews_router
from app.api.v1.rules import router as rules_router
from app.api.v1.status import router as status_router

__all__ = [
    "agent_router",
    "antifraude_router",
    "audit_router",
    "auth_router",
    "claims_reviews_router",
    "claims_router",
    "conversations_router",
    "documents_router",
    "health_router",
    "imports_router",
    "insights_router",
    "network_router",
    "rules_router",
    "status_router",
]
