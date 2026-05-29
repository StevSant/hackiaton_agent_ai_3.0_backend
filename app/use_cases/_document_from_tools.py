"""Build a `DocumentEvent` from tool results collected during an agent turn.

Called AFTER the compose phase and BEFORE `DoneEvent`, mirroring the same
pattern as `_chart_from_tools.maybe_build_chart`.

Returns None when no `crear_documento` tool fired during the turn.
"""

from __future__ import annotations

from typing import Any

from app.schemas.chat.stream.document_data import DocumentData
from app.schemas.chat.stream.document_event import DocumentEvent


def maybe_build_document(
    tool_results: list[dict[str, Any]],
) -> DocumentEvent | None:
    """Return a DocumentEvent when the `crear_documento` tool fired, else None.

    When multiple calls fired (unlikely but possible) the last one wins —
    it represents the most-refined version the LLM produced.
    """
    last: dict[str, Any] | None = None
    for tr in tool_results:
        if tr.get("tool") != "crear_documento":
            continue
        result = tr.get("result")
        if isinstance(result, dict) and result.get("titulo") and result.get("contenido_markdown"):
            last = result

    if last is None:
        return None

    return DocumentEvent(
        data=DocumentData(
            titulo=str(last["titulo"]),
            contenido_markdown=str(last["contenido_markdown"]),
        )
    )
