from pydantic import BaseModel


class ModeratorTokenData(BaseModel):
    delta: str
