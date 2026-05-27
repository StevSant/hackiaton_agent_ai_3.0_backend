"""Tool for Q2 — '¿Por qué este siniestro fue marcado como alto riesgo?'.

Returns the full `ClaimDetail` including activations (rules fired), ml_factors
(top SHAP contributors) and similar narratives — the three pillars of the
explainability accordion (spec §6 V8).
"""

from pydantic import BaseModel

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.schemas.claim import ClaimDetail


class GetClaimDetailInput(BaseModel):
    claim_id: str


class GetClaimDetailOutput(BaseModel):
    found: bool
    claim: ClaimDetail | None = None


class GetClaimDetailTool:
    name = "get_claim_detail"
    description = (
        "Devuelve el desglose completo de un siniestro: reglas activadas, factores "
        "del modelo y narrativas similares. Úsalo cuando el usuario pida explicación de un caso."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return GetClaimDetailInput.model_json_schema()

    async def run(self, args: GetClaimDetailInput) -> GetClaimDetailOutput:
        detail = await self._queries.get_detail(args.claim_id)
        return GetClaimDetailOutput(found=detail is not None, claim=detail)
