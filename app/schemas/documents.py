"""API response schemas for document upload."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UploadedDocument(BaseModel):
    """Returned by POST /claims/{id}/documentos on success."""

    tipo: str
    estado: str = "entregado"
    filename: str
    path: str
    signed_url: str


class BulkUploadResult(BaseModel):
    """Returned by POST /claims/{id}/documentos/bulk."""

    uploaded: list[UploadedDocument] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
