from pydantic import BaseModel


class PanelRosterEntry(BaseModel):
    agent_id: str
    display_name: str
    lens: str
