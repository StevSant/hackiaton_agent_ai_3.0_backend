from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.agent_verdict_data import AgentVerdictData


class AgentVerdictEvent(BaseModel):
    type: Literal["agent_verdict"] = "agent_verdict"
    data: AgentVerdictData
