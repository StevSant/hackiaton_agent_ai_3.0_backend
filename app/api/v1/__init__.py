from app.api.v1.agent import router as agent_router
from app.api.v1.auth import auth_router
from app.api.v1.claims import router as claims_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.reviews import antifraude_router, claims_reviews_router
from app.api.v1.rules import router as rules_router
from app.api.v1.status import router as status_router

__all__ = [
    "agent_router",
    "antifraude_router",
    "auth_router",
    "claims_reviews_router",
    "claims_router",
    "documents_router",
    "health_router",
    "rules_router",
    "status_router",
]
