"""Agent SSE endpoint — streams real OpenAI responses token-by-token."""
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.chat.request import AgentAskRequest

agent_router = APIRouter(prefix="/agent", tags=["agent"])

SYSTEM_PROMPT = """Eres Centinela IA, el asistente de análisis antifraude de Aseguradora del Sur (Ecuador).

Tu rol:
- Ayudas a analistas e investigadores de fraude a entender, priorizar y explicar siniestros sospechosos.
- Tienes acceso a datos de siniestros, alertas IA, scores de fraude (0-100) y patrones de comportamiento.
- Citas evidencia concreta: IDs de siniestro, códigos de alerta (RF01, AF02...), montos, fechas, proveedores.
- Eres directo, técnico y conciso. No haces suposiciones que no se apoyen en datos.
- Nunca acusas a asegurados — surfaceas casos que requieren revisión especializada.

Contexto del sistema: Aseguradora del Sur opera en Ecuador. Los ramos principales son vehículos, salud, hogar y vida.
Las alertas de fraude se codifican como RF (reglas de fraude) y AF (anomalías IA).
El score de fraude va de 0 (bajo riesgo) a 100 (alto riesgo); rojo ≥ 70, amarillo 40-69, verde < 40.
"""


async def _stream_openai(messages: list[dict]) -> AsyncIterator[str]:
    """Yields SSE-formatted lines from OpenAI chat completions stream."""
    try:
        from openai import AsyncOpenAI  # type: ignore[import-untyped]

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())  # type: ignore[union-attr]
        message_id = str(uuid.uuid4())

        stream = await client.chat.completions.create(
            model=settings.LLM_DEFAULT_MODEL,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
            max_tokens=800,
            temperature=0.3,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                event = {"type": "token", "data": {"delta": delta.content, "message_id": message_id}}
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        done = {"type": "done", "data": {"message_id": message_id}}
        yield f"data: {json.dumps(done)}\n\n"

    except Exception as exc:  # noqa: BLE001
        error = {"type": "error", "data": {"code": "llm_error", "message": str(exc)}}
        yield f"data: {json.dumps(error)}\n\n"


def _build_messages(request: AgentAskRequest) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for turn in request.history[-10:]:  # keep last 10 turns
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})

    if request.context_claim_id:
        messages.append(
            {
                "role": "system",
                "content": f"El analista está revisando actualmente el siniestro {request.context_claim_id}.",
            }
        )

    messages.append({"role": "user", "content": request.message})
    return messages


@agent_router.post("/ask")
async def agent_ask(body: AgentAskRequest) -> StreamingResponse:
    messages = _build_messages(body)

    return StreamingResponse(
        _stream_openai(messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
