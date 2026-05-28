"""Tool for Q7 — '¿Qué documentos faltan en los casos críticos?'."""

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.agents.claims_agent.tools.types import MissingDocClaim, TierFilter


class MissingDocumentsInput(BaseModel):
    tier: TierFilter = "amarillo+rojo"
    top_n: int = Field(10, ge=1, le=50)
    filter_claim_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst is asking about a specific case in scope. "
            "Usually injected automatically from the UI context."
        ),
    )


class MissingDocumentsOutput(BaseModel):
    tier: TierFilter
    claims: list[MissingDocClaim]


class MissingDocumentsTool:
    name = "missing_documents"
    description = (
        "Lista los siniestros críticos con documentación legal incompleta, indicando "
        "qué documentos faltan en cada caso."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return MissingDocumentsInput.model_json_schema()

    async def run(self, args: MissingDocumentsInput) -> MissingDocumentsOutput:
        if args.filter_claim_id is not None:
            detail = await self._queries.get_detail(args.filter_claim_id)
            if detail is None:
                return MissingDocumentsOutput(tier=args.tier, claims=[])
            faltantes = [d.tipo for d in detail.documentos if d.falta]
            scoped = [
                MissingDocClaim(
                    claim_id=detail.id,
                    nivel=str(detail.nivel),
                    score=detail.score,
                    documentos_faltantes=faltantes,
                )
            ]
            return MissingDocumentsOutput(tier=args.tier, claims=scoped)

        rows = await self._queries.missing_documents(top_n=args.top_n, tier=args.tier)
        return MissingDocumentsOutput(tier=args.tier, claims=rows)
