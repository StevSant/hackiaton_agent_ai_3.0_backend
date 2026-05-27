"""Upload a document for a given claim (siniestro).

Re-added per user request — overrides §11/§13 deferral; OPTIONAL feature.
Validates size + MIME, stores to the configured adapter (Supabase or in-memory),
returns a signed URL valid for 1 hour.
"""

from __future__ import annotations

import re
import uuid

from app.core.config import settings
from app.core.errors import ValidationFailed
from app.infrastructure.storage.ports import Storage
from app.schemas.documents import UploadedDocument


def _safe_filename(name: str) -> str:
    """Strip path traversal + collapse non-alphanum to underscores."""
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return re.sub(r"[^\w.\-]", "_", base) or "archivo"


async def upload_claim_document(
    *,
    storage: Storage,
    id_siniestro: str,
    data: bytes,
    filename: str,
    content_type: str,
    tipo: str,
) -> UploadedDocument:
    """Validate and store one document; return the upload record with a signed URL."""

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

    return UploadedDocument(
        tipo=tipo,
        estado="entregado",
        filename=safe_name,
        path=path_within_bucket,
        signed_url=url,
    )
