import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.schemas.auth import CurrentUser, LoginRequest, LoginResponse

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# Build in-memory user registry from seed config (no DB needed for demo)
def _build_user_registry() -> dict[str, dict]:
    registry: dict[str, dict] = {}
    for user in settings.seed_users():
        email = user.get("email", "").lower()
        if email:
            registry[email] = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, email)),
                "email": email,
                "password": user.get("password", ""),
                "full_name": user.get("full_name", email),
                "role": user.get("role", "analista"),
            }
    return registry


_USERS = _build_user_registry()


def _check_password(plain: str, stored: str) -> bool:
    """Simple comparison for demo; production should use bcrypt."""
    try:
        import bcrypt  # type: ignore[import-untyped]
        if stored.startswith("$2"):
            return bcrypt.checkpw(plain.encode(), stored.encode())
    except ImportError:
        pass
    return plain == stored


def _create_token(user: dict) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user["full_name"],
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET.get_secret_value(), algorithm=settings.JWT_ALGORITHM)


@auth_router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    email = body.email.lower()
    user = _USERS.get(email)

    if not user or not _check_password(body.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    token = _create_token(user)
    return LoginResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_TTL_MINUTES * 60,
        user=CurrentUser(
            id=user["id"],
            email=user["email"],
            role=user["role"],
            full_name=user["full_name"],
        ),
    )


@auth_router.get("/me")
async def me_stub() -> dict:
    """Placeholder — requires auth middleware wired."""
    return {"detail": "Usar el JWT devuelto por /login para verificar identidad."}
