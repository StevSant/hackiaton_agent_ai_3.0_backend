"""Tool — ficha completa de un asegurado.

Returns the insured person's profile (segment, city, mora flag, KPIs) and the
top-N claims by score so the agent can ground itself before answering
entity-focused follow-up questions.
"""

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.schemas.asegurados import AseguradoOut
from app.schemas.claim import ClaimSummary


class GetAseguradoDetailInput(BaseModel):
    asegurado_id: str = Field(..., min_length=1)


class GetAseguradoDetailOutput(BaseModel):
    found: bool
    asegurado: AseguradoOut | None = None
    top_claims: list[ClaimSummary] = []


class GetAseguradoDetailTool:
    name = "get_asegurado_detail"
    description = (
        "Devuelve la ficha completa de un asegurado (segmento, ciudad, antigüedad, "
        "indicador de mora, frecuencia de reclamos) más los siniestros con mayor "
        "score de alerta. Usalo al inicio de una conversación enfocada en un "
        "asegurado específico para conocer su perfil antes de hacer preguntas de "
        "seguimiento."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return GetAseguradoDetailInput.model_json_schema()

    async def run(self, args: GetAseguradoDetailInput) -> GetAseguradoDetailOutput:
        result = await self._queries.get_asegurado_detail(
            args.asegurado_id, top_claims=5
        )
        if result is None:
            return GetAseguradoDetailOutput(found=False)
        return GetAseguradoDetailOutput(
            found=True,
            asegurado=result.asegurado,
            top_claims=result.top_claims,
        )
