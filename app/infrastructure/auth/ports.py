from typing import Protocol, runtime_checkable

from app.infrastructure.auth.types import User


@runtime_checkable
class AuthVerifier(Protocol):
    async def verify(self, jwt: str) -> User: ...
