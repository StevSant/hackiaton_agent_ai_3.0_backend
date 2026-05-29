from pydantic import BaseModel

from app.schemas.panel.specialist_rebuttal import SpecialistRebuttal


class AgentRebuttalData(BaseModel):
    agent_id: str
    rebuttal: SpecialistRebuttal
