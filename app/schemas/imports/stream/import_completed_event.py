from typing import Literal

from pydantic import BaseModel


class ImportCompletedData(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class ImportCompletedEvent(BaseModel):
    type: Literal["import.completed"] = "import.completed"
    data: ImportCompletedData
