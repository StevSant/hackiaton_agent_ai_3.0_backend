from typing import Literal

from pydantic import BaseModel, Field

ColumnAlign = Literal["left", "right", "center"]
ColumnKind = Literal["text", "number", "money", "tier", "mono", "citation"]


class TableColumn(BaseModel):
    key: str
    label: str
    align: ColumnAlign = "left"
    col_kind: ColumnKind = "text"


class TableVisual(BaseModel):
    """A sortable, multi-column table. Values are pre-formatted by the backend
    except numeric kinds, which the frontend may right-align/format."""

    kind: Literal["table"] = "table"
    message_id: str
    title: str
    columns: list[TableColumn]
    rows: list[dict[str, str | float | None]]
    citations: list[str] = Field(default_factory=list)
