from app.api.v1.agent import agent_router
from app.api.v1.auth import auth_router
from app.api.v1.health import router as health_router

__all__ = ["agent_router", "auth_router", "health_router"]
