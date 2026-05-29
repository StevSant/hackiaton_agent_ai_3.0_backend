from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.moderator_token_data import ModeratorTokenData


class ModeratorTokenEvent(BaseModel):
    type: Literal["moderator_token"] = "moderator_token"
    data: ModeratorTokenData
