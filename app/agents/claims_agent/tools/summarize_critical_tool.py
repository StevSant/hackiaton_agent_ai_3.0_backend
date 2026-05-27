"""Tool for Q11 — 'Genera un resumen ejecutivo de los casos críticos'."""

from pydantic import BaseModel

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.agents.claims_agent.tools.types import ExecutiveSummary


class SummarizeCriticalInput(BaseModel):
    pass  # no args — the summary is a fixed snapshot


class SummarizeCriticalOutput(BaseModel):
    summary: ExecutiveSummary


class SummarizeCriticalTool:
    name = "summarize_critical"
    description = (
        "Genera un resumen ejecutivo con el total de siniestros, distribución por nivel, "
        "top-N en rojo y proveedores/ramos más recurrentes."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return SummarizeCriticalInput.model_json_schema()

    async def run(self, args: SummarizeCriticalInput) -> SummarizeCriticalOutput:
        summary = await self._queries.executive_summary()
        return SummarizeCriticalOutput(summary=summary)
