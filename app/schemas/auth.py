from __future__ import annotations

from pydantic import BaseModel

from app.domain.auth.role import Role


class LoginRequest(BaseModel):
    """JSON body for POST /auth/login (Angular client)."""

    email: str
    password: str


class CurrentUser(BaseModel):
    """User summary embedded in the login response and usable in UI."""

    id: str
    email: str
    role: Role
    full_name: str


class LoginResponse(BaseModel):
    """Returned by both login endpoints."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105  # not a secret — standard OAuth2 field
    expires_in: int  # seconds
    user: CurrentUser
