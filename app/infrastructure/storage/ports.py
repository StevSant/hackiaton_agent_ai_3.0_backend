from typing import Protocol, runtime_checkable

from app.infrastructure.storage.types import StoredObject


@runtime_checkable
class Storage(Protocol):
    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObject: ...

    async def signed_url(self, *, key: str, expires_in: int = 3600) -> str: ...

    async def delete(self, *, key: str) -> None: ...
