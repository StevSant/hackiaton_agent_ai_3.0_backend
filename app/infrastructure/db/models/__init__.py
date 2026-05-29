"""Import all ORM models so Base.metadata and Alembic autogenerate see them.

Order matters: tables with FK targets must be imported before their dependents
if you need SQLAlchemy's mapper to resolve forward-references at module load time.
The order here is: no-deps → polizas (→ asegurados) → siniestros → rest.
"""

from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.audit_event import AuditEvent
from app.infrastructure.db.models.claim_narrative import ClaimNarrative
from app.infrastructure.db.models.claim_review import ClaimReview
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.conversation import Conversation
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.message import Message
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.rule_change import RuleChange
from app.infrastructure.db.models.rule_override import RuleOverride
from app.infrastructure.db.models.siniestro import Siniestro

__all__ = [
    "Asegurado",
    "AuditEvent",
    "ClaimNarrative",
    "ClaimReview",
    "ClaimScore",
    "Conversation",
    "Documento",
    "Message",
    "Poliza",
    "Proveedor",
    "RuleChange",
    "RuleOverride",
    "Siniestro",
]
