from typing import Literal

from pydantic import BaseModel


class CaseStartedData(BaseModel):
    claim_id: str
    row_index: int


class CaseStartedEvent(BaseModel):
    type: Literal["case.started"] = "case.started"
    data: CaseStartedData
