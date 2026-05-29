from typing import Annotated

from pydantic import Field

from app.schemas.chat.stream.agent_step_event import AgentStepEvent
from app.schemas.chat.stream.chart_event import ChartEvent
from app.schemas.chat.stream.document_event import DocumentEvent
from app.schemas.chat.stream.done_event import DoneEvent
from app.schemas.chat.stream.error_event import ErrorEvent
from app.schemas.chat.stream.token_event import TokenEvent
from app.schemas.chat.stream.tool_call_event import ToolCallEvent
from app.schemas.chat.stream.tool_result_event import ToolResultEvent

ChatStreamEvent = Annotated[
    TokenEvent
    | ToolCallEvent
    | ToolResultEvent
    | AgentStepEvent
    | ChartEvent
    | DocumentEvent
    | ErrorEvent
    | DoneEvent,
    Field(discriminator="type"),
]
