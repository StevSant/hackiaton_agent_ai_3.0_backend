"""Tool for Q11 — 'Genera un resumen ejecutivo de los casos críticos'."""

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.agents.claims_agent.tools.query_claims_tool import _detail_to_summary
from app.agents.claims_agent.tools.types import ExecutiveSummary


class SummarizeCriticalInput(BaseModel):
    filter_claim_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst is asking about a specific case in scope. "
            "Usually injected automatically from the UI context."
        ),
    )
    filter_provider_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst asks about 'este proveedor' while a provider "
            "context is active. Injected automatically by the dispatcher."
        ),
    )
    filter_asegurado_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst asks about 'este asegurado' while an asegurado "
            "context is active. Injected automatically by the dispatcher."
        ),
    )


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
        if args.filter_claim_id is not None:
            detail = await self._queries.get_detail(args.filter_claim_id)
            if detail is not None:
                claim_summary = _detail_to_summary(detail)
                tier = detail.nivel.value  # "verde" | "amarillo" | "rojo"
                summary = ExecutiveSummary(
                    total_claims=1,
                    rojo_count=1 if tier == "rojo" else 0,
                    amarillo_count=1 if tier == "amarillo" else 0,
                    verde_count=1 if tier == "verde" else 0,
                    top_rojo=[claim_summary] if tier == "rojo" else [],
                    top_proveedores=[detail.proveedor] if detail.proveedor else [],
                    top_ramos=[detail.ramo],
                )
                return SummarizeCriticalOutput(summary=summary)

        summary = await self._queries.executive_summary()
        return SummarizeCriticalOutput(summary=summary)
