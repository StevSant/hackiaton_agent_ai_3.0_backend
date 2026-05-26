from typing import Any
from uuid import UUID

from pydantic import BaseModel


class VectorRecord(BaseModel):
    owner_id: UUID
    source_type: str
    source_id: UUID
    chunk_index: int
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = {}
