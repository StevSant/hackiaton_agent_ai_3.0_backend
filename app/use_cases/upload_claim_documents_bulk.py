"""Bulk upload helper for multiple claim documents."""

from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.storage.ports import Storage
from app.schemas.documents import BulkUploadResult, UploadedDocument
from app.use_cases.claim_score_persist import rescore_claim_persisted
from app.use_cases.upload_claim_document import upload_claim_document


async def upload_claim_documents_bulk(
    *,
    session: AsyncSession,
    storage: Storage,
    id_siniestro: str,
    files: list[UploadFile],
    workspace_id: UUID | None = None,
) -> BulkUploadResult:
    """Upload many files for one claim, collecting per-file errors."""
    uploaded: list[UploadedDocument] = []
    errors: list[str] = []

    for upload in files:
        filename = upload.filename or "archivo"
        try:
            data = await upload.read()
            result = await upload_claim_document(
                session=session,
                storage=storage,
                id_siniestro=id_siniestro,
                data=data,
                filename=filename,
                content_type=upload.content_type or "application/octet-stream",
                tipo="otro",
                workspace_id=workspace_id,
                rescore_after_upload=False,
                commit=False,
            )
            uploaded.append(result)
        except Exception as exc:  # collect per-file failures
            errors.append(f"{filename}: {exc}")

    if uploaded:
        await rescore_claim_persisted(session, id_siniestro)
        await session.commit()

    return BulkUploadResult(uploaded=uploaded, errors=errors)
