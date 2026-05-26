from pydantic import BaseModel


class TokenData(BaseModel):
    delta: str
    message_id: str
