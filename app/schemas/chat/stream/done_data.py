from pydantic import BaseModel


class DoneData(BaseModel):
    message_id: str
