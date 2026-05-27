from typing import Any

from pydantic import BaseModel


class ToolSpecView(BaseModel):
    """Tool catalog entry shown to the LLM in the ReAct prompt.

    Slim projection of a tool: name + description + JSON-Schema for args. The
    LLM uses this catalog to pick the right tool and the right args. We
    serialize this into the react prompt so the LLM sees exactly what each
    tool accepts.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
