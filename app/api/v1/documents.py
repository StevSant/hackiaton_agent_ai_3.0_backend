"""Documents API — THIN router: parse → use case → return.

Routes:
    POST   /claims/{id}/documentos             → UploadedDocument  (any authenticated user)
    DELETE /claims/{id}/documentos?path=<path> → 204 No Content    (any authenticated user)

Re-added per user request — overrides §11/§13 deferral; OPTIONAL feature.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Response, UploadFile

from app.api.deps import get_current_user, get_storage
from app.domain.auth.user import User
from app.infrastructure.storage.ports import Storage
from app.schemas.documents import UploadedDocument
from app.use_cases.delete_claim_document import delete_claim_document
from app.use_cases.upload_claim_document import upload_claim_document

router = APIRouter(prefix="/claims", tags=["documentos"])


@router.post("/{claim_id}/documentos", response_model=UploadedDocument, status_code=201)
async def upload_document_route(
    claim_id: str,
    file: UploadFile,
    tipo: Annotated[str, Form()] = "otro",
    storage: Annotated[Storage, Depends(get_storage)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> UploadedDocument:
    data = await file.read()
    return await upload_claim_document(
        storage=storage,
        id_siniestro=claim_id,
        data=data,
        filename=file.filename or "archivo",
        content_type=file.content_type or "application/octet-stream",
        tipo=tipo,
    )


@router.delete("/{claim_id}/documentos", status_code=204)
async def delete_document_route(
    claim_id: str,
    path: Annotated[
        str,
        Query(description="Relative bucket path returned by the upload endpoint."),
    ],
    storage: Annotated[Storage, Depends(get_storage)] = ...,  # type: ignore[assignment]
    _user: Annotated[User, Depends(get_current_user)] = ...,  # type: ignore[assignment]
) -> Response:
    await delete_claim_document(storage=storage, id_siniestro=claim_id, path=path)
    return Response(status_code=204)
