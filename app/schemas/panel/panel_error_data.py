from pydantic import BaseModel


class PanelErrorData(BaseModel):
    agent_id: str | None = None
    code: str
    message: str
