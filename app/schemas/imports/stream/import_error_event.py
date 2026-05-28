from typing import Literal

from pydantic import BaseModel


class ImportErrorData(BaseModel):
    row_index: int | None = None
    claim_id: str | None = None
    message: str


class ImportErrorEvent(BaseModel):
    type: Literal["import.error"] = "import.error"
    data: ImportErrorData
