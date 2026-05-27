from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import settings
from app.core.errors import Unauthorized
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.auth.ports import AuthVerifier


class JwtIssuer(AuthVerifier):
    """Issues and verifies HS256 JWTs.

    This is the concrete adapter behind the ``AuthVerifier`` port.
    Reads algorithm / secret / TTL from ``settings`` — never from arguments.
    """

    def issue(self, user: User) -> str:
        """Return a signed JWT for *user*.  Called by the login use case."""
        now = datetime.now(tz=UTC)
        exp = now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
        payload: dict[str, str | int] = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "full_name": user.full_name,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM,
        )

    async def verify(self, token: str) -> User:
        """Decode and validate *token*, returning the domain User.

        Raises ``Unauthorized`` on any failure (expired, invalid sig, missing claims).
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET.get_secret_value(),
                algorithms=[settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError as exc:
            raise Unauthorized("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise Unauthorized(f"Invalid token: {exc}") from exc

        try:
            return User(
                id=UUID(payload["sub"]),
                email=str(payload["email"]),
                role=Role(payload["role"]),
                full_name=str(payload["full_name"]),
            )
        except (KeyError, ValueError) as exc:
            raise Unauthorized(f"Malformed token payload: {exc}") from exc
