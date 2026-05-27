from typing import Literal

ReActAction = Literal["use_tool", "finish"]
"""LLM's chosen action at a ReAct step.

- `use_tool`: invoke a tool from the registry; the LLM must also provide
  `tool` (name) and `args` (input matching the tool's pydantic schema).
- `finish`: enough info has been gathered; exit the loop and compose the answer.
"""
