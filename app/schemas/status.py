"""Wire shape for `GET /api/v1/status/ai` — observability of the AI stack.

Surfaces which adapters loaded successfully so the team (and jurors during the
demo "show the architecture" moment) can see at a glance what's configured.
"""

from pydantic import BaseModel


class AIStatusResponse(BaseModel):
    """Snapshot of the AI stack pinned to `app.state.ai` at lifespan startup."""

    llm_provider: str
    llm_model: str
    embeddings_provider: str
    embeddings_model: str
    embeddings_dim: int
    embeddings_loaded: bool
    vector_store: str
    fraud_model_path: str
    fraud_model_present: bool
    anomaly_model_path: str
    anomaly_model_present: bool
    prompts_loaded: list[str]
    similarity_threshold_fs13: float
