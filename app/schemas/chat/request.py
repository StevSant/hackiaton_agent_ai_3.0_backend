from pydantic import BaseModel, Field, model_validator

from app.schemas.agent import DocumentContext

_MAX_QUERY_LENGTH = 4000


class AgentAskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_QUERY_LENGTH)
    conversation_id: str | None = None
    context_claim_id: str | None = None
    context_provider_id: str | None = None
    context_asegurado_id: str | None = None
    # Optional document the analyst is editing. Carries its own large content
    # field so "Mejorá el documento: ..." can ride the main chat without the
    # markdown blowing the 4000-char `message` cap.
    document_context: DocumentContext | None = None
    history: list[dict] = []

    @model_validator(mode="after")
    def _single_focus(self) -> "AgentAskRequest":
        set_count = sum(
            v is not None
            for v in (
                self.context_claim_id,
                self.context_provider_id,
                self.context_asegurado_id,
            )
        )
        if set_count > 1:
            raise ValueError(
                "only one of context_claim_id / _provider_id / _asegurado_id may be set"
            )
        return self
