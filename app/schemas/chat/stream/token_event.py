from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.token_data import TokenData


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    data: TokenData
