from pydantic import BaseModel

from app.schemas.panel.specialist_verdict import SpecialistVerdict


class AgentVerdictData(BaseModel):
    agent_id: str
    verdict: SpecialistVerdict
