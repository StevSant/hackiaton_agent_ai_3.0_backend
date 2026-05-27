"""API response schemas for document upload.

Re-added per user request — overrides §11/§13 deferral; OPTIONAL feature.
"""

from __future__ import annotations

from pydantic import BaseModel


class UploadedDocument(BaseModel):
    """Returned by POST /claims/{id}/documentos on success."""

    tipo: str
    estado: str = "entregado"
    filename: str
    path: str
    signed_url: str
