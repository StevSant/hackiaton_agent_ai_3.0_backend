"""Tool — análisis de dictámenes por analista (A3).

Aggregates the antifraude unit's verdicts (dictámenes) per analyst: how many
cases each dictated and the breakdown of outcomes. Lets the agent answer
questions about reviewer workload and decision patterns. This describes
analyst activity — never a person's guilt.
"""

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.agents.claims_agent.tools.types import ReviewerStats


class AnalyzeReviewersInput(BaseModel):
    top_n: int = Field(default=20, ge=1, le=100)


class AnalyzeReviewersOutput(BaseModel):
    reviewers: list[ReviewerStats] = []


class AnalyzeReviewersTool:
    name = "analyze_reviewers"
    description = (
        "Resume los dictámenes emitidos por cada analista de la unidad antifraude "
        "(cuántos casos dictaminó y el desglose de resultados: sospecha confirmada, "
        "descartado, requiere más información). Úsalo para preguntas sobre carga de "
        "trabajo o patrones de decisión de los revisores. Describe actividad de "
        "revisión, no culpabilidad de personas."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return AnalyzeReviewersInput.model_json_schema()

    async def run(self, args: AnalyzeReviewersInput) -> AnalyzeReviewersOutput:
        rows = await self._queries.analyze_reviewers(top_n=args.top_n)
        return AnalyzeReviewersOutput(reviewers=rows)
