from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.auth.password_hasher import hash_password, verify_password

if TYPE_CHECKING:
    pass


class _SeededUser:
    """Internal holder for a hashed user entry.  Never leaves this module."""

    __slots__ = ("hashed_password", "user")

    def __init__(self, user: User, hashed_password: str) -> None:
        self.user = user
        self.hashed_password = hashed_password


class EnvSeededUserRepo:
    """Parses ``AUTH_SEED_USERS`` JSON at construction time.

    Passwords are bcrypt-hashed immediately and the plaintext is discarded.
    The hash is never written to disk or logged.

    Expected JSON schema:
        [{"email": "...", "password": "...", "role": "analista|antifraude", "full_name": "..."}]
    """

    def __init__(self, seed_users_json: str) -> None:
        raw: list[dict[str, str]] = json.loads(seed_users_json)
        self._store: dict[str, _SeededUser] = {}
        for entry in raw:
            user = User(
                id=uuid.uuid5(uuid.NAMESPACE_URL, entry["email"]),
                email=entry["email"],
                role=Role(entry["role"]),
                full_name=entry["full_name"],
            )
            self._store[entry["email"]] = _SeededUser(
                user=user,
                hashed_password=hash_password(entry["password"]),
            )

    def get_by_email(self, email: str) -> User | None:
        """Return the User for *email*, or None if not found."""
        entry = self._store.get(email)
        return entry.user if entry else None

    def verify_credentials(self, email: str, password: str) -> User | None:
        """Return the User if credentials match, else None."""
        entry = self._store.get(email)
        if entry is None:
            return None
        if not verify_password(password, entry.hashed_password):
            return None
        return entry.user
