"""Claims import router — POST /claims/import.

Accepts a multipart file upload (CSV or JSON) and bulk-upserts every claim
into the database.  Gated to the ``antifraude`` role because it performs bulk
DB writes.

Format detection is based on file extension:
    *.json      → JSON parser
    *.csv       → CSV parser
    anything else → attempts JSON first, then CSV

Returns an ``ImportResult`` summary: imported / skipped / errors.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.schemas.imports import ImportResult
from app.use_cases.import_claims import import_claims, parse_csv, parse_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["claims"])

_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Bulk-import claims from a CSV or JSON file",
    status_code=status.HTTP_200_OK,
)
async def import_claims_route(
    file: Annotated[UploadFile, File(description="CSV or JSON claim file (≤ 50 MB)")],
    _user: Annotated[User, Depends(require_role(Role.antifraude))],
    session: Annotated[AsyncSession | None, Depends(_get_optional_session)] = None,
) -> ImportResult:
    """Upload a CSV or JSON file and upsert every claim into the database.

    The file format is detected from the filename extension (.csv / .json).
    A JSON file must contain an array of ClaimDetail-compatible objects (same
    shape as ``data/synthetic/claims.json``).  A CSV file must include the
    columns documented in ``app/use_cases/import_claims/_parsers.py``.

    Every claim is scored independently; a parse or DB error on one row does NOT
    abort the batch — it is reported in ``errors`` and counted in ``skipped``.
    """
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

    result = await import_claims(session, records=records)
    logger.info(
        "POST /claims/import: file=%s imported=%d skipped=%d",
        file.filename, result.imported, result.skipped,
    )
    return result


def _detect_and_parse(content: bytes, filename: str, content_type: str) -> list:  # type: ignore[type-arg]
    """Detect format from filename/content-type and delegate to the right parser."""
    is_csv = (
        filename.endswith(".csv")
        or "csv" in content_type
    )
    is_json = (
        filename.endswith(".json")
        or "json" in content_type
    )

    if is_json:
        return parse_json(content)
    if is_csv:
        return parse_csv(content)

    # Unknown extension — try JSON first, then CSV
    try:
        return parse_json(content)
    except ValueError:
        pass
    return parse_csv(content)


# ---------------------------------------------------------------------------
# DB session dependency — reuses the same optional-session pattern from deps.py
# ---------------------------------------------------------------------------


from collections.abc import AsyncIterator  # noqa: E402 — after router definition


async def _get_optional_session() -> AsyncIterator[AsyncSession | None]:
    """Yield an AsyncSession when the factory is initialised, else yield None."""
    import app.infrastructure.db.engine as _engine  # avoid circular at module load

    sf = getattr(_engine, "_session_factory", None)
    if sf is None:
        yield None
        return
    async with sf() as sess:
        yield sess
