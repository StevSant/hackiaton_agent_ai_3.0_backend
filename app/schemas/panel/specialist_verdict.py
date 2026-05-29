from pydantic import BaseModel, Field

from app.schemas.risk import Confianza, Tier


class SpecialistVerdict(BaseModel):
    """One specialist's R1 verdict (LLM structured output). Never accuses."""

    nivel: Tier
    dictamen: str  # always framed as "posible…" / "requiere revisión"
    puntos_clave: list[str] = Field(default_factory=list)
    confianza: Confianza = "media"
    citas: list[str] = Field(default_factory=list)  # claim ids / rule codes
