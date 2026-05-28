from pydantic import BaseModel, model_validator


class AgentAskRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    context_claim_id: str | None = None
    context_provider_id: str | None = None
    context_asegurado_id: str | None = None
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
