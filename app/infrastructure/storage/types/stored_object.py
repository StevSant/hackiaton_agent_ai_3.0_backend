from pydantic import BaseModel


class StoredObject(BaseModel):
    key: str
    size_bytes: int
    content_type: str
