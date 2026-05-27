"""Claims import router — POST /claims/import + template download."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_store, get_current_user, require_any_role
from app.core.config import settings
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.audit import InMemoryAuditStore
from app.schemas.audit import AuditAction
from app.schemas.imports import ImportResult
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.import_claims import import_claims, parse_csv, parse_json

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
    file: Annotated[UploadFile, File(description="CSV or JSON claim file (≤ 50 MB)")],
    user: Annotated[
        User,
        Depends(require_any_role(Role.analista, Role.antifraude)),
    ],
    audit: Annotated[InMemoryAuditStore, Depends(get_audit_store)],
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
        records = _detect_and_parse(content, filename, content_type)
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
    emit_audit_event(
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


def _detect_and_parse(content: bytes, filename: str, content_type: str) -> list:  # type: ignore[type-arg]
    """Detect format from filename/content-type and delegate to the right parser."""
    is_csv = filename.endswith(".csv") or "csv" in content_type
    is_json = filename.endswith(".json") or "json" in content_type

    if is_json:
        return parse_json(content)
    if is_csv:
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
