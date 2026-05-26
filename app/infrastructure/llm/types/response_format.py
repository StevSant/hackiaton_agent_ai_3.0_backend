from typing import Any

from pydantic import BaseModel


class ResponseFormat(BaseModel):
    schema_name: str
    json_schema: dict[str, Any]
