from typing import Literal

from pydantic import BaseModel


class ImportStartedData(BaseModel):
    total_rows: int
    filename: str


class ImportStartedEvent(BaseModel):
    type: Literal["import.started"] = "import.started"
    data: ImportStartedData
