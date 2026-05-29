from pydantic import BaseModel


class PanelDoneData(BaseModel):
    claim_id: str
