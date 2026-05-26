from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.error_data import ErrorData


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    data: ErrorData
