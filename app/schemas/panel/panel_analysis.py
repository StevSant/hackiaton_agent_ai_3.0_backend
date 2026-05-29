from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.panel.panel_consensus import PanelConsensus
from app.schemas.panel.panel_lane_snapshot import PanelLaneSnapshot


class PanelAnalysis(BaseModel):
    """Cached result of a multi-agent panel debate, surfaced on the claim.

    Advisory only — never overwrites the engine-derived score. Stores the full
    lane snapshots (incl. narration) so the cached view replays the debate.
    """

    lanes: list[PanelLaneSnapshot] = Field(default_factory=list)
    moderator_text: str = ""
    consensus: PanelConsensus | None = None
    generated_at: datetime
