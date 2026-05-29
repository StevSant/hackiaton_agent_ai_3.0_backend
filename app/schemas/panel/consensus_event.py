from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.consensus_data import ConsensusData


class ConsensusEvent(BaseModel):
    type: Literal["consensus"] = "consensus"
    data: ConsensusData
