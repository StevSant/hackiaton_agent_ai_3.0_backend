"""Agent SSE endpoint — streams `ChatStreamEvent` from the LangGraph claims agent.

The legacy wire shape (`message` / `history` / `context_claim_id`) used by the
Angular client (`agent.store.ts`) is preserved here and adapted on entry to the
use-case shape (`query` / `context.focus_claim_id` / `conversation_id`) expected
by `AskAgent`. `history` is intentionally dropped: multi-turn memory is owned by
the LangGraph checkpointer keyed by `conversation_id`.

This route holds zero business logic and never imports an LLM SDK directly —
it delegates to `AskAgent` (ReAct loop + 5 tools wired in `deps.py`), which goes
through the `LLMProvider` port.
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.api.deps import (
    get_ask_agent,
    get_audit_store,
    get_current_user,
    get_llm,
    get_speech_transcriber,
)
from app.core.config import settings
from app.domain.auth.user import User
from app.infrastructure.audit import AuditStore
from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.speech.ports import SpeechTranscriber
from app.schemas.agent import AgentAskContext
from app.schemas.agent import AgentAskRequest as AskAgentRequest
from app.schemas.audit import AuditAction, AuditActor
from app.schemas.chat.request import AgentAskRequest as WireAgentAskRequest
from app.schemas.chat.tts import TtsRequest
from app.schemas.speech import TranscribeResponse
from app.use_cases.ask_agent import AskAgent
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.transcribe_audio import transcribe_audio

router = APIRouter(prefix="/agent", tags=["agent"])


def _to_use_case_request(wire: WireAgentAskRequest) -> AskAgentRequest:
    has_context = (
        wire.context_claim_id is not None
        or wire.context_provider_id is not None
        or wire.context_asegurado_id is not None
    )
    context = (
        AgentAskContext(
            focus_claim_id=wire.context_claim_id,
            focus_provider_id=wire.context_provider_id,
            focus_asegurado_id=wire.context_asegurado_id,
        )
        if has_context
        else None
    )
    return AskAgentRequest(
        query=wire.message,
        context=context,
        conversation_id=wire.conversation_id,
    )


async def _stream_events(
    ask_agent: AskAgent, req: AskAgentRequest, user: User
) -> AsyncIterator[str]:
    async for event in ask_agent.run(req, user=user):
        payload = event.model_dump(mode="json")
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/transcribe", response_model=TranscribeResponse)
async def agent_transcribe(
    file: UploadFile,
    transcriber: Annotated[SpeechTranscriber, Depends(get_speech_transcriber)],
    _user: Annotated[User, Depends(get_current_user)],
) -> TranscribeResponse:
    data = await file.read()
    return await transcribe_audio(
        transcriber=transcriber,
        data=data,
        filename=file.filename or "audio.webm",
        content_type=file.content_type or "application/octet-stream",
    )


@router.post("/tts")
async def agent_tts(
    body: TtsRequest,
    llm: Annotated[LLMProvider, Depends(get_llm)],
    _user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Synthesize text to MP3 speech via TTS.

    Returns raw audio/mpeg bytes. Text is capped at settings.TTS_MAX_CHARS (5 000)
    characters; longer payloads are rejected with HTTP 422.
    """
    if len(body.text) > settings.TTS_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "text_too_long",
                "message": f"Text must be at most {settings.TTS_MAX_CHARS} characters.",
            },
        )
    voice = body.voice or settings.TTS_VOICE
    audio = await llm.synthesize_speech(body.text, voice)
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/ask")
async def agent_ask(
    body: WireAgentAskRequest,
    ask_agent: Annotated[AskAgent, Depends(get_ask_agent)],
    user: Annotated[User, Depends(get_current_user)],
    audit: Annotated[AuditStore, Depends(get_audit_store)],
) -> StreamingResponse:
    req = _to_use_case_request(body)
    preview = body.message.strip().replace("\n", " ")
    if len(preview) > 160:
        preview = preview[:157] + "..."
    if body.context_claim_id:
        title = f"Preguntó a Centinela IA sobre {body.context_claim_id}"
        audit_target = body.context_claim_id
    elif body.context_provider_id:
        title = f"Preguntó a Centinela IA sobre el proveedor {body.context_provider_id}"
        audit_target = body.context_provider_id
    elif body.context_asegurado_id:
        title = f"Preguntó a Centinela IA sobre el asegurado {body.context_asegurado_id}"
        audit_target = body.context_asegurado_id
    else:
        title = "Consultó a Centinela IA"
        audit_target = None
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.consulta_ia,
        title=title,
        detail=preview,
        target=audit_target,
        actor=AuditActor.agente,
    )
    return StreamingResponse(
        _stream_events(ask_agent, req, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
