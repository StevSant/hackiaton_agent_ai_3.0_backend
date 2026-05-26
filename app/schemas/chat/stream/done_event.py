from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.done_data import DoneData


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    data: DoneData
