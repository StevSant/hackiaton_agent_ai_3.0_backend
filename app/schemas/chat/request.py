from pydantic import BaseModel


class AgentAskRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    context_claim_id: str | None = None
    history: list[dict] = []
