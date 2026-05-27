from pydantic import BaseModel, Field

from app.schemas.claim import ClaimSummary


class ExecutiveSummary(BaseModel):
    """Aggregate snapshot of the most critical claims (Q11)."""

    total_claims: int
    rojo_count: int
    amarillo_count: int
    verde_count: int
    top_rojo: list[ClaimSummary] = Field(default_factory=list)
    top_proveedores: list[str] = Field(default_factory=list)
    top_ramos: list[str] = Field(default_factory=list)
