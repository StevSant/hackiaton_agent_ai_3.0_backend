"""In-memory Storage adapter for offline dev, tests, and smoke checks.

Implements the Storage Protocol without any external service.
`signed_url` returns a fake ``memory://`` URL — sufficient for smoke tests
and local UI development that doesn't follow signed links.
"""

from __future__ import annotations

from app.infrastructure.storage.types import StoredObject


class InMemoryStorage:
    """Process-local dict-backed Storage.  Not safe for multi-process deployments."""

    def __init__(self) -> None:
        # key → (data, content_type)
        self._store: dict[str, tuple[bytes, str]] = {}

    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject:
        self._store[key] = (data, content_type)
        return StoredObject(key=key, size_bytes=len(data), content_type=content_type)

    async def signed_url(self, *, key: str, expires_in: int = 3600) -> str:
        # Return a deterministic fake URL; the `expires_in` param is accepted but ignored.
        return f"memory://{key}?expires_in={expires_in}"

    async def delete(self, *, key: str) -> None:
        self._store.pop(key, None)
