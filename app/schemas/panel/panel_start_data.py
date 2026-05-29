from pydantic import BaseModel, Field

from app.schemas.panel.panel_roster_entry import PanelRosterEntry


class PanelStartData(BaseModel):
    claim_id: str
    roster: list[PanelRosterEntry] = Field(default_factory=list)
