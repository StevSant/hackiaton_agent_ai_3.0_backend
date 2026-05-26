from typing import Protocol, runtime_checkable
from uuid import UUID

from app.infrastructure.vectorstore.types import VectorQueryResult, VectorRecord


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, records: list[VectorRecord]) -> None: ...

    async def query(
        self,
        *,
        owner_id: UUID,
        embedding: list[float],
        top_k: int = 5,
        source_type: str | None = None,
    ) -> list[VectorQueryResult]: ...

    async def delete(self, *, owner_id: UUID, source_id: UUID) -> None: ...
