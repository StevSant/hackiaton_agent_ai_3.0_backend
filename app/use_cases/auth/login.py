from __future__ import annotations

from app.core.config import settings
from app.core.errors import Unauthorized
from app.infrastructure.auth.env_seeded_user_repo import EnvSeededUserRepo
from app.infrastructure.auth.jwt_issuer import JwtIssuer
from app.schemas.auth import CurrentUser, LoginResponse


class LoginUseCase:
    """Verify credentials and issue a JWT.

    Shared by both login endpoints (JSON + OAuth2 form).
    """

    def __init__(self, repo: EnvSeededUserRepo, issuer: JwtIssuer) -> None:
        self._repo = repo
        self._issuer = issuer

    def execute(self, email: str, password: str) -> LoginResponse:
        user = self._repo.verify_credentials(email, password)
        if user is None:
            raise Unauthorized("Invalid email or password")
        token = self._issuer.issue(user)
        return LoginResponse(
            access_token=token,
            token_type="bearer",  # noqa: S106  # not a secret — standard OAuth2 field
            expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
            user=CurrentUser(
                id=str(user.id),
                email=user.email,
                role=user.role,
                full_name=user.full_name,
            ),
        )
