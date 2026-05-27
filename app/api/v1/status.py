"""GET /api/v1/status/ai — surfaces the lifespan-pinned AI stack.

Cheap, no auth (matches /health). Lets the demo show "the AI stack is configured
and reachable" without having to ask an LLM question. Also useful for the team
to spot misconfiguration at boot (e.g. ML model artifact missing).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_ai_state
from app.core.config import settings
from app.core.lifespan_state import AIState
from app.schemas.status import AIStatusResponse

router = APIRouter(prefix="/status", tags=["status"])

_KNOWN_PROMPTS = ("claims_system", "route", "compose")


@router.get("/ai", response_model=AIStatusResponse)
def ai_status(state: Annotated[AIState, Depends(get_ai_state)]) -> AIStatusResponse:
    loaded_prompts: list[str] = []
    for name in _KNOWN_PROMPTS:
        try:
            state.prompts.load(name, "v1")
            loaded_prompts.append(f"{name}.v1")
        except FileNotFoundError:
            continue

    return AIStatusResponse(
        llm_provider=state.llm_provider,
        llm_model=state.llm_model,
        embeddings_provider=settings.EMBEDDINGS_PROVIDER,
        embeddings_model=state.embeddings_model,
        embeddings_dim=state.embeddings_dim,
        embeddings_loaded=state.embeddings is not None,
        vector_store=settings.VECTOR_STORE,
        fraud_model_path=settings.FRAUD_MODEL_PATH,
        fraud_model_present=state.fraud_model_present,
        anomaly_model_path=settings.ANOMALY_MODEL_PATH,
        anomaly_model_present=state.anomaly_model_present,
        prompts_loaded=loaded_prompts,
        similarity_threshold_fs13=settings.SIMILARITY_THRESHOLD_FS13,
    )
