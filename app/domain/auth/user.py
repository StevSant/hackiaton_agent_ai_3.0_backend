from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.domain.auth.role import Role


class User(BaseModel):
    """Authenticated user — pure domain object, no I/O."""

    id: UUID
    email: str
    role: Role
    full_name: str
