"""merge workspace + coords heads

Revision ID: cc22cbf44cf3
Revises: 0004_claim_import_workspace, 0004_siniestro_coords
Create Date: 2026-05-27 10:13:52.967306+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'cc22cbf44cf3'
down_revision: str | None = ('0004_claim_import_workspace', '0004_siniestro_coords')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
