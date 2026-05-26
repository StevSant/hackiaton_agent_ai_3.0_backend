from pydantic import BaseModel

from app.infrastructure.llm.types.role import Role


class Message(BaseModel):
    role: Role
    content: str
    name: str | None = None
