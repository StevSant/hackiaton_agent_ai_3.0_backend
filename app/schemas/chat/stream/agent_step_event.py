from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.agent_step_data import AgentStepData


class AgentStepEvent(BaseModel):
    type: Literal["agent_step"] = "agent_step"
    data: AgentStepData
