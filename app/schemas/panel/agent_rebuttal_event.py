from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.agent_rebuttal_data import AgentRebuttalData


class AgentRebuttalEvent(BaseModel):
    type: Literal["agent_rebuttal"] = "agent_rebuttal"
    data: AgentRebuttalData
