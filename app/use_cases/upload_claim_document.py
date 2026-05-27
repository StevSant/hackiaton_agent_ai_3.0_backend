"""Upload a document for a given claim (siniestro).

Validates size + MIME, stores to the configured adapter (Supabase or in-memory),
persists the documento row, and returns a signed URL valid for 1 hour.
"""

from __future__ import annotations

import re
import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFound, ValidationFailed
from app.infrastructure.db.models.siniestro import Siniestro
from app.infrastructure.storage.ports import Storage
from app.schemas.documents import UploadedDocument
from app.use_cases.sync_claim_document import persist_uploaded_document


def _safe_filename(name: str) -> str:
    """Strip path traversal + collapse non-alphanum to underscores."""
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return re.sub(r"[^\w.\-]", "_", base) or "archivo"


def _can_access_claim(sin: Siniestro | None, workspace_id: UUID | None) -> bool:
    if sin is None:
        return False
    if workspace_id is None:
        return True
    return sin.workspace_id is None or sin.workspace_id == workspace_id


async def upload_claim_document(
    *,
    session: AsyncSession,
    storage: Storage,
    id_siniestro: str,
    data: bytes,
    filename: str,
    content_type: str,
    tipo: str,
    workspace_id: UUID | None = None,
) -> UploadedDocument:
    """Validate and store one document; persist metadata and return upload record."""
    sin = await session.get(Siniestro, id_siniestro)
    if not _can_access_claim(sin, workspace_id):
        raise NotFound(f"Siniestro {id_siniestro!r} no encontrado")

    if len(data) > settings.UPLOAD_MAX_BYTES:
        raise ValidationFailed(
            f"Archivo excede el tamaño máximo permitido "
            f"({settings.UPLOAD_MAX_BYTES // (1024 * 1024)} MB)."
        )

    if content_type not in settings.UPLOAD_ALLOWED_MIME:
        raise ValidationFailed(
            f"Tipo de archivo no permitido: {content_type!r}. "
            f"Tipos aceptados: {', '.join(settings.UPLOAD_ALLOWED_MIME)}."
        )

    safe_name = _safe_filename(filename)
    unique_prefix = uuid.uuid4().hex[:8]
    path_within_bucket = f"{id_siniestro}/{unique_prefix}_{safe_name}"
    key = f"{settings.SUPABASE_STORAGE_BUCKET}/{path_within_bucket}"

    await storage.put(key=key, data=data, content_type=content_type)
    url = await storage.signed_url(key=key, expires_in=3600)

    doc = await persist_uploaded_document(
        session,
        id_siniestro=id_siniestro,
        tipo=tipo,
        storage_path=path_within_bucket,
        filename=safe_name,
        content_type=content_type,
    )
    await session.commit()

    return UploadedDocument(
        tipo=doc.tipo_documento,
        estado="entregado",
        filename=safe_name,
        path=path_within_bucket,
        signed_url=url,
    )
