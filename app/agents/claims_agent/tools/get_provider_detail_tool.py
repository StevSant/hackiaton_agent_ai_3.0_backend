"""Tool — ficha completa de un proveedor/beneficiario.

Returns the provider's identity, risk KPIs, ramos, restrictive-list indicator,
and the top-N claims by score so the agent can answer entity-focused questions
without calling multiple broad tools first.
"""

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.schemas.claim import ClaimSummary
from app.schemas.network import ProviderOut


class GetProviderDetailInput(BaseModel):
    provider_id: str = Field(..., min_length=1)


class GetProviderDetailOutput(BaseModel):
    found: bool
    provider: ProviderOut | None = None
    top_claims: list[ClaimSummary] = []


class GetProviderDetailTool:
    name = "get_provider_detail"
    description = (
        "Devuelve la ficha completa de un proveedor (identidad, KPIs de riesgo, "
        "ramos donde aparece, indicador de lista restrictiva) más los siniestros "
        "asociados con mayor score. Usalo al inicio de una conversación enfocada "
        "en un proveedor específico para conocer su perfil antes de hacer preguntas "
        "de seguimiento."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return GetProviderDetailInput.model_json_schema()

    async def run(self, args: GetProviderDetailInput) -> GetProviderDetailOutput:
        result = await self._queries.get_provider_detail(
            args.provider_id, top_claims=5
        )
        if result is None:
            return GetProviderDetailOutput(found=False)
        return GetProviderDetailOutput(
            found=True,
            provider=result.provider,
            top_claims=result.top_claims,
        )
