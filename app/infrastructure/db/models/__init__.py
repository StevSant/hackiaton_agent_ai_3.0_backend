"""Import all ORM models so Base.metadata and Alembic autogenerate see them.

Order matters: tables with FK targets must be imported before their dependents
if you need SQLAlchemy's mapper to resolve forward-references at module load time.
The order here is: no-deps → polizas (→ asegurados) → siniestros → rest.
"""

from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_narrative import ClaimNarrative
from app.infrastructure.db.models.claim_review import ClaimReview
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro

__all__ = [
    "Asegurado",
    "ClaimNarrative",
    "ClaimReview",
    "ClaimScore",
    "Documento",
    "Poliza",
    "Proveedor",
    "Siniestro",
]
