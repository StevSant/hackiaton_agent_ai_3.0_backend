from typing import Literal

from pydantic import BaseModel


class ParseRowData(BaseModel):
    row_index: int        # 0-based position in the input
    claim_id: str
    ramo: str
    cobertura: str


class ParseRowEvent(BaseModel):
    type: Literal["parse.row"] = "parse.row"
    data: ParseRowData
