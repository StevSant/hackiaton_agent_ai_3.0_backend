from typing import Annotated

from pydantic import Field

from app.schemas.panel.agent_rebuttal_event import AgentRebuttalEvent
from app.schemas.panel.agent_token_event import AgentTokenEvent
from app.schemas.panel.agent_verdict_event import AgentVerdictEvent
from app.schemas.panel.consensus_event import ConsensusEvent
from app.schemas.panel.moderator_token_event import ModeratorTokenEvent
from app.schemas.panel.panel_done_event import PanelDoneEvent
from app.schemas.panel.panel_error_event import PanelErrorEvent
from app.schemas.panel.panel_start_event import PanelStartEvent

PanelStreamEvent = Annotated[
    PanelStartEvent
    | AgentTokenEvent
    | AgentVerdictEvent
    | AgentRebuttalEvent
    | ModeratorTokenEvent
    | ConsensusEvent
    | PanelErrorEvent
    | PanelDoneEvent,
    Field(discriminator="type"),
]
