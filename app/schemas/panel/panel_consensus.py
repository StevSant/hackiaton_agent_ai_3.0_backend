from pydantic import BaseModel, Field

from app.schemas.risk import Tier


class PanelConsensus(BaseModel):
    """Moderator synthesis. Action is ALWAYS a human-review framing (spec §2.10)."""

    nivel_final: Tier
    nivel_de_acuerdo: float = Field(..., ge=0.0, le=1.0)
    puntos_de_conflicto: list[str] = Field(default_factory=list)
    resumen: str
    accion_recomendada: str
    posible_falso_positivo: bool = False
