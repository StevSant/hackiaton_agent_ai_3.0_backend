from pydantic import BaseModel


class MissingDocClaim(BaseModel):
    """One claim from `missing_documents_tool` — claim ID + which docs are missing."""

    claim_id: str
    nivel: str  # tier label "verde"/"amarillo"/"rojo"
    score: int
    documentos_faltantes: list[str]
