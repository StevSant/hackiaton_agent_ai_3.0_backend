from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.agent_token_data import AgentTokenData


class AgentTokenEvent(BaseModel):
    type: Literal["agent_token"] = "agent_token"
    data: AgentTokenData
