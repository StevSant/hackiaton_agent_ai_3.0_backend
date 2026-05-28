"""Documents API — THIN router: parse → use case → return."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_store, get_current_user, get_storage
from app.core.config import settings
from app.domain.auth.user import User
from app.infrastructure.audit import AuditStore
from app.infrastructure.storage.ports import Storage
from app.schemas.audit import AuditAction
from app.schemas.documents import BulkUploadResult, UploadedDocument
from app.use_cases.delete_claim_document import delete_claim_document
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.upload_claim_document import upload_claim_document
from app.use_cases.upload_claim_documents_bulk import upload_claim_documents_bulk

router = APIRouter(prefix="/claims", tags=["documentos"])


async def _get_optional_session() -> AsyncIterator[AsyncSession]:
    import app.infrastructure.db.engine as engine

    session_factory = getattr(engine, "_session_factory", None)
    if session_factory is None:
        from app.core.errors import ProviderError

        raise ProviderError("Database session is not available")
    async with session_factory() as session:
        yield session


@router.post("/{claim_id}/documentos", response_model=UploadedDocument, status_code=201)
async def upload_document_route(
    claim_id: str,
    file: UploadFile,
    tipo: Annotated[str, Form()] = "otro",
    storage: Annotated[Storage, Depends(get_storage)] = ...,  # type: ignore[assignment]
    audit: Annotated[AuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(_get_optional_session)] = ...,  # type: ignore[assignment]
) -> UploadedDocument:
    data = await file.read()
    workspace_id = user.id if settings.AUTH_ENABLED else None
    uploaded = await upload_claim_document(
        session=session,
        storage=storage,
        id_siniestro=claim_id,
        data=data,
        filename=file.filename or "archivo",
        content_type=file.content_type or "application/octet-stream",
        tipo=tipo,
        workspace_id=workspace_id,
    )
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.apertura,
        title=f"Subió documento a {claim_id}",
        detail=f"Tipo: {tipo} · archivo: {file.filename or 'sin nombre'}",
        target=claim_id,
    )
    return uploaded


@router.post(
    "/{claim_id}/documentos/bulk",
    response_model=BulkUploadResult,
    status_code=201,
)
async def upload_documents_bulk_route(
    claim_id: str,
    files: Annotated[list[UploadFile], File(description="PDFs or images for the claim")],
    storage: Annotated[Storage, Depends(get_storage)] = ...,  # type: ignore[assignment]
    audit: Annotated[AuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(_get_optional_session)] = ...,  # type: ignore[assignment]
) -> BulkUploadResult:
    workspace_id = user.id if settings.AUTH_ENABLED else None
    result = await upload_claim_documents_bulk(
        session=session,
        storage=storage,
        id_siniestro=claim_id,
        files=files,
        workspace_id=workspace_id,
    )
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.apertura,
        title=f"Subió {len(files)} documentos a {claim_id}",
        detail=f"Aceptados: {len(result.uploaded)} · rechazados: {len(result.errors)}",
        target=claim_id,
    )
    return result


@router.delete("/{claim_id}/documentos", status_code=204)
async def delete_document_route(
    claim_id: str,
    path: Annotated[
        str,
        Query(description="Relative bucket path returned by the upload endpoint."),
    ],
    storage: Annotated[Storage, Depends(get_storage)] = ...,  # type: ignore[assignment]
    audit: Annotated[AuditStore, Depends(get_audit_store)] = ...,  # type: ignore[assignment]
    user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
    session: Annotated[AsyncSession, Depends(_get_optional_session)] = ...,  # type: ignore[assignment]
) -> Response:
    workspace_id = user.id if settings.AUTH_ENABLED else None
    await delete_claim_document(
        session=session,
        storage=storage,
        id_siniestro=claim_id,
        path=path,
        workspace_id=workspace_id,
    )
    await emit_audit_event(
        audit,
        user=user,
        action=AuditAction.cierre,
        title=f"Eliminó un documento de {claim_id}",
        detail=f"Ruta: {path}",
        target=claim_id,
    )
    return Response(status_code=204)
