from app.api.v1.agent import router as agent_router
from app.api.v1.auth import router as auth_router
from app.api.v1.claims import router as claims_router
from app.api.v1.health import router as health_router
from app.api.v1.rules import router as rules_router
from app.api.v1.status import router as status_router

__all__ = [
    "agent_router",
    "auth_router",
    "claims_router",
    "health_router",
    "rules_router",
    "status_router",
]
