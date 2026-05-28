"""Claims import router — POST /claims/import (sync) + POST /claims/import/stream (SSE)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_anomaly_detector,
    get_audit_store,
    get_fraud_classifier,
    get_llm,
    require_any_role,
)
from app.core.config import settings
from app.domain.anomaly import AnomalyDetector
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.domain.ml import FraudClassifier
from app.infrastructure.audit import AuditStore
from app.infrastructure.llm import LLMProvider
from app.schemas.audit import AuditAction
from app.schemas.claim import ClaimDetail
from app.schemas.imports import ImportResult
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.import_claims import (
    import_claims,
    parse_csv,
    parse_docx,
    parse_json,
    parse_pdf,
    parse_xlsx,
)
from app.use_cases.import_claims_stream import stream_import_claims

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["claims"])

_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit
_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "samples" / "claims.sample.csv"
)


@router.get(
    "/import/template",
    summary="Download the CSV template for bulk claim import",
)
async def download_import_template_route(
    _user: Annotated[
        User,
        Depends(require_any_role(Role.analista, Role.antifraude)),
    ],
) -> FileResponse:
    if not _TEMPLATE_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "template_missing", "message": "Plantilla CSV no disponible"},
        )
    return FileResponse(
        path=_TEMPLATE_PATH,
        media_type="text/csv",
        filename="claims.sample.csv",
    )


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Bulk-import claims from a CSV or JSON file",
    status_code=status.HTTP_200_OK,
)
async def import_claims_route(
    file: Annotated[UploadFile, File(description="CSV / JSON / XLSX / PDF / DOCX claim file (≤ 50 MB)")],
    user: Annotated[
        User,
        Depends(require_any_role(Role.analista, Role.antifraude)),
    ],
    audit: Annotated[AuditStore, Depends(get_audit_store)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    session: Annotated[AsyncSession | None, Depends(_get_optional_session)] = None,
) -> ImportResult:
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "db_unavailable",
                "message": (
                    "Database session is not available. "
                    "Set CLAIMS_SOURCE=db and ensure the DB is reachable."
                ),
            },
        )

    content = await file.read(_MAX_FILE_BYTES + 1)
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "file_too_large", "message": "Maximum file size is 50 MB"},
        )

    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    try:
        records = await _detect_and_parse(content, filename, content_type, llm=llm)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "parse_error", "message": str(exc)},
        ) from exc

    workspace_id = user.id if settings.AUTH_ENABLED else None
    result = await import_claims(session, records=records, workspace_id=workspace_id)
    logger.info(
        "POST /claims/import: file=%s imported=%d skipped=%d",
        file.filename,
        result.imported,
        result.skipped,
    )
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.apertura,
        title=f"Importó {result.imported} siniestros desde archivo",
        detail=(
            f"Archivo: {file.filename or 'sin nombre'} · "
            f"importados {result.imported} · omitidos {result.skipped}"
        ),
    )
    return result


async def _detect_and_parse(
    content: bytes,
    filename: str,
    content_type: str,
    *,
    llm: LLMProvider | None,
) -> list[ClaimDetail]:
    """Detect format from filename/content-type and delegate to the right parser.

    Async because PDF/DOCX parsers run pdfplumber/python-docx in threads and
    invoke the LLM for structured field extraction.
    """
    name = filename.lower()
    ct = content_type.lower()

    if name.endswith(".json") or "json" in ct:
        return parse_json(content)
    if name.endswith(".xlsx") or "spreadsheetml" in ct:
        return parse_xlsx(content)
    if name.endswith(".pdf") or "pdf" in ct:
        if llm is None:
            raise ValueError("Importar PDF requiere proveedor LLM configurado")
        return await parse_pdf(content, llm=llm)
    if name.endswith(".docx") or "wordprocessingml" in ct:
        if llm is None:
            raise ValueError("Importar DOCX requiere proveedor LLM configurado")
        return await parse_docx(content, llm=llm)
    if name.endswith(".csv") or "csv" in ct:
        return parse_csv(content)

    try:
        return parse_json(content)
    except ValueError:
        pass
    return parse_csv(content)


async def _get_optional_session() -> AsyncIterator[AsyncSession | None]:
    import app.infrastructure.db.engine as _engine

    sf = getattr(_engine, "_session_factory", None)
    if sf is None:
        yield None
        return
    async with sf() as sess:
        yield sess


@router.post(
    "/import/stream",
    summary="Bulk-import claims with real-time SSE progress stream",
)
async def import_claims_stream_route(
    request: Request,
    user: Annotated[
        User,
        Depends(require_any_role(Role.analista, Role.antifraude)),
    ],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    session: Annotated[AsyncSession | None, Depends(_get_optional_session)] = None,
    fraud_classifier: Annotated[FraudClassifier | None, Depends(get_fraud_classifier)] = None,
    anomaly_detector: Annotated[AnomalyDetector | None, Depends(get_anomaly_detector)] = None,
) -> StreamingResponse:
    """SSE endpoint: parses + scores + (optionally) persists claims one at a time.

    Unlike the sync ``POST /import``, this endpoint works in dry-run mode when no
    DB session is available: claims are scored and events are streamed, but nothing
    is persisted. ``case.completed.data.persisted`` will be ``false`` in that case.
    """
    body = await request.body()
    if len(body) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "file_too_large", "message": "Maximum file size is 50 MB"},
        )

    content_type = request.headers.get("content-type", "").lower()
    content_disposition = request.headers.get("content-disposition", "").lower()
    filename = ""
    if "filename=" in content_disposition:
        filename = content_disposition.split("filename=")[-1].strip().strip('"').strip("'")

    try:
        records = await _detect_and_parse(body, filename, content_type, llm=llm)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "parse_error", "message": str(exc)},
        ) from exc

    # Resolve NarrativeSimilarity from lifespan state — skip when unavailable.
    similarity = _get_similarity_from_state(request)

    workspace_id = user.id if settings.AUTH_ENABLED else None

    async def _event_source() -> AsyncIterator[str]:
        async for event in await stream_import_claims(
            records=records,
            filename=filename or "claims",
            session=session,
            similarity=similarity,
            fraud_classifier=fraud_classifier,
            anomaly_detector=anomaly_detector,
            workspace_id=workspace_id,
        ):
            yield f"data: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"

    logger.info(
        "POST /claims/import/stream: file=%s rows=%d user=%s",
        filename or "<body>",
        len(records),
        user.email,
    )
    return StreamingResponse(
        _event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _get_similarity_from_state(request: Request) -> object | None:
    """Return the NarrativeSimilarity adapter from app.state when available."""
    from app.domain.similarity import NarrativeSimilarity as _Port

    state = getattr(request.app.state, "ai", None)
    if state is None:
        return None
    similarity = getattr(state, "similarity", None)
    if similarity is not None and isinstance(similarity, _Port):
        return similarity
    return None
