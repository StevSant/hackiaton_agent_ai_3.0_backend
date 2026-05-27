from typing import Any

from pydantic import BaseModel


class ResponseFormat(BaseModel):
    """Wire spec for an LLM JSON-schema response.

    `strict=False` (default) sends the schema as guidance — adapters pass it
    verbatim and rely on the caller's post-hoc pydantic validation. `strict=True`
    asks the provider to enforce the schema exactly; OpenAI strict mode is the
    canonical example. Adapters that support strict mode normalize the schema
    (closing objects, listing all properties in `required`, stripping `default`)
    before dispatch. Use `strict=False` for schemas with open-ended dict fields
    (e.g. tool-arg payloads) since strict mode forbids `additionalProperties: true`.
    """

    schema_name: str
    json_schema: dict[str, Any]
    strict: bool = False
