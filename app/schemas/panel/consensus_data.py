from pydantic import BaseModel

from app.schemas.panel.panel_consensus import PanelConsensus


class ConsensusData(BaseModel):
    consensus: PanelConsensus
