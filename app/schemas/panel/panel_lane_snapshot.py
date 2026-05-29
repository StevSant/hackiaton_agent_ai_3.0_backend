from pydantic import BaseModel

from app.schemas.panel.specialist_rebuttal import SpecialistRebuttal
from app.schemas.panel.specialist_verdict import SpecialistVerdict


class PanelLaneSnapshot(BaseModel):
    """One specialist's full lane after a panel run — enough to replay it statically."""

    agent_id: str
    display_name: str
    lens: str
    narracion: str = ""
    verdict: SpecialistVerdict | None = None
    rebuttal_narracion: str = ""
    rebuttal: SpecialistRebuttal | None = None
    # True when this specialist's R1 verdict failed (the lane has no real opinion).
    failed: bool = False
