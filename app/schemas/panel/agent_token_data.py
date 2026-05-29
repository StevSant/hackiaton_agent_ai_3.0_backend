from typing import Literal

from pydantic import BaseModel


class AgentTokenData(BaseModel):
    agent_id: str
    round: Literal[1, 2]
    delta: str
