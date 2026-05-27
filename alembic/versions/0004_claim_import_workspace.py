"""0004_claim_import_workspace — workspace scoping + document storage metadata.

Revision ID: 0004_claim_import_workspace
Revises: 0003_add_conversations
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_claim_import_workspace"
down_revision: str | None = "0003_add_conversations"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "siniestros",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_siniestros_workspace_id",
        "siniestros",
        ["workspace_id"],
        unique=False,
    )

    op.add_column(
        "documentos",
        sa.Column("storage_path", sa.String(512), nullable=True),
    )
    op.add_column(
        "documentos",
        sa.Column("filename", sa.String(255), nullable=True),
    )
    op.add_column(
        "documentos",
        sa.Column("content_type", sa.String(120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documentos", "content_type")
    op.drop_column("documentos", "filename")
    op.drop_column("documentos", "storage_path")
    op.drop_index("ix_siniestros_workspace_id", table_name="siniestros")
    op.drop_column("siniestros", "workspace_id")
