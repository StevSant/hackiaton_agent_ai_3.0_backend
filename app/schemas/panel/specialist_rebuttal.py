from pydantic import BaseModel

from app.schemas.risk import Tier


class SpecialistRebuttal(BaseModel):
    """A specialist's R2 reaction after reading peers' verdicts."""

    ajuste: str  # what they concede / push back on
    nivel_actualizado: Tier
    cambia_postura: bool
