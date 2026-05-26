from typing import Any
from uuid import UUID

from pydantic import BaseModel


class VectorQueryResult(BaseModel):
    id: UUID
    source_type: str
    source_id: UUID
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] = {}
