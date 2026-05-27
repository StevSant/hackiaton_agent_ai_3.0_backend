"""Wire schema for the rules catalog endpoints.

Mirrors `domain/rules/ports.RuleMeta` but keeps the domain dataclass decoupled
from FastAPI / Pydantic serialisation.  Fields match the catalog contract
defined in design spec §10 and the frontend `RulesCatalogStore`.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.risk import Tier


class RuleMetaOut(BaseModel):
    """Catalog entry returned by GET /rules/catalog and GET /rules/{code}."""

    code: str
    name: str
    tier_hint: Tier
    short_description: str
    what_triggers: str
    max_points: int
