"""Semantic search over claim narratives — RAG tool.

Embeds the query and retrieves the most similar claim descriptions via
pgvector cosine similarity.  Reuses the existing FS-13 embedding
infrastructure (``NarrativeSimilarity.nearest_by_text``).
"""

from pydantic import BaseModel, Field

from app.domain.similarity import NarrativeSimilarity
from app.schemas.risk import SimilarClaim


class SearchNarrativesInput(BaseModel):
    query: str = Field(
        description=(
            "Texto de búsqueda semántica — describe la dinámica, patrón "
            "o modus operandi que buscas entre los siniestros."
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número máximo de resultados.",
    )


class SearchNarrativesOutput(BaseModel):
    results: list[SimilarClaim]
    total: int


class SearchNarrativesTool:
    name = "search_narratives"
    description = (
        "Búsqueda semántica en las descripciones de siniestros. Encuentra casos "
        "con narrativas similares al texto dado — útil para detectar patrones, "
        "dinámicas recurrentes o modus operandi compartidos entre reclamos."
    )

    def __init__(self, similarity: NarrativeSimilarity) -> None:
        self._similarity = similarity

    @property
    def input_schema(self) -> dict[str, object]:
        return SearchNarrativesInput.model_json_schema()

    async def run(self, args: SearchNarrativesInput) -> SearchNarrativesOutput:
        results = await self._similarity.nearest_by_text(
            args.query, top_k=args.top_k,
        )
        return SearchNarrativesOutput(results=results, total=len(results))
