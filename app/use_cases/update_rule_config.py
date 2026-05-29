"""update_rule_config — apply a dashboard edit to one fraud rule.

Sequence (antifraude-only; gated at the route):
1. Validate the code exists and any threshold keys are known + numeric.
2. Persist the new override row (enabled flag + threshold overlay).
3. Re-hydrate the engine loader so the change takes effect immediately.
4. Append an audit entry to the rule-change log (one per changed aspect).
5. Run a full rescore so every existing claim reflects the change at once.
6. Return the refreshed RuleConfigOut row.

No threshold edit can inject arbitrary keys: only the numeric keys already present
in the rule's ``config.yaml`` block are accepted, and values must be >= 0.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ValidationFailed
from app.domain.rules.catalog import get_meta
from app.domain.rules.defaults import DEFAULT_DISABLED_CODES
from app.domain.rules.loader import numeric_thresholds
from app.domain.rules.ports import RuleMeta
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.rule_changes import RuleChangesStore
from app.infrastructure.rule_overrides import RuleOverrideRecord, RuleOverridesStore
from app.schemas.rule_changes import RuleChangeKind, RuleChangeOut
from app.schemas.rules_config import RuleConfigOut, RuleConfigPatch
from app.use_cases.hydrate_rule_overrides import hydrate_rule_overrides
from app.use_cases.list_rules_config import list_rules_config
from app.use_cases.rescore_all import rescore_all


def _config_key(code: str) -> str:
    return code.replace("-", "_")


def _validate_thresholds(code: str, thresholds: dict[str, float]) -> None:
    """Reject unknown keys, non-numeric, or negative threshold values."""
    allowed = numeric_thresholds(_config_key(code))
    if not allowed:
        raise ValidationFailed(f"La regla {code} no tiene umbrales configurables.")
    unknown = set(thresholds) - set(allowed)
    if unknown:
        raise ValidationFailed(
            f"Umbrales desconocidos para {code}: {', '.join(sorted(unknown))}. "
            f"Permitidos: {', '.join(sorted(allowed))}."
        )
    for key, value in thresholds.items():
        if value < 0:
            raise ValidationFailed(f"El umbral '{key}' no puede ser negativo.")


def _build_changes(
    meta: RuleMeta,
    *,
    actor: str,
    prev_enabled: bool,
    new_enabled: bool,
    prev_thresholds: dict[str, float],
    new_thresholds: dict[str, float],
) -> list[RuleChangeOut]:
    """Emit one change-log entry per aspect that actually changed."""
    now = datetime.now(tz=UTC)
    changes: list[RuleChangeOut] = []

    if new_enabled != prev_enabled:
        kind = RuleChangeKind.reactivada if new_enabled else RuleChangeKind.pausada
        verb = "Reactivó" if new_enabled else "Pausó"
        changes.append(
            RuleChangeOut(
                id=uuid4().hex,
                ts=now,
                actor=actor,
                rule_code=meta.code,
                rule_name=meta.name,
                kind=kind,
                summary=f"{verb} la regla {meta.code}.",
                before_value="activa" if prev_enabled else "pausada",
                after_value="activa" if new_enabled else "pausada",
            )
        )

    changed_keys = {
        k: v for k, v in new_thresholds.items() if prev_thresholds.get(k) != v
    }
    if changed_keys:
        changes.append(
            RuleChangeOut(
                id=uuid4().hex,
                ts=now,
                actor=actor,
                rule_code=meta.code,
                rule_name=meta.name,
                kind=RuleChangeKind.umbral,
                summary=(
                    f"Ajustó umbrales de {meta.code}: "
                    f"{', '.join(f'{k}={v:g}' for k, v in changed_keys.items())}."
                ),
                before_value=json.dumps(
                    {k: prev_thresholds.get(k) for k in changed_keys}, default=str
                ),
                after_value=json.dumps(changed_keys, default=str),
            )
        )

    return changes


async def update_rule_config(
    session: AsyncSession,
    *,
    code: str,
    patch: RuleConfigPatch,
    overrides_store: RuleOverridesStore,
    changes_store: RuleChangesStore,
    actor: str,
    similarity: NarrativeSimilarity | None = None,
    decoder: VehicleDecoder | None = None,
) -> RuleConfigOut:
    meta = get_meta(code)
    if meta is None:
        raise NotFound(f"Regla '{code}' no encontrada")

    if patch.enabled is None and patch.thresholds is None:
        raise ValidationFailed("Debes indicar 'enabled' y/o 'thresholds'.")

    current = await overrides_store.get(code)
    prev_enabled = (
        current.enabled if current is not None else code not in DEFAULT_DISABLED_CODES
    )
    prev_thresholds: dict[str, float] = (
        dict(current.thresholds) if current is not None else {}
    )

    new_enabled = patch.enabled if patch.enabled is not None else prev_enabled
    new_thresholds = prev_thresholds
    if patch.thresholds is not None:
        _validate_thresholds(code, patch.thresholds)
        new_thresholds = {**prev_thresholds, **patch.thresholds}

    record: RuleOverrideRecord = await overrides_store.upsert(
        code,
        enabled=new_enabled,
        thresholds=new_thresholds,
        updated_by=actor,
    )

    # Re-hydrate the engine from the full persisted state, then log + rescore.
    await hydrate_rule_overrides(overrides_store)

    for change in _build_changes(
        meta,
        actor=actor,
        prev_enabled=prev_enabled,
        new_enabled=record.enabled,
        prev_thresholds=prev_thresholds,
        new_thresholds=record.thresholds,
    ):
        await changes_store.append(change)

    # Immediate full rescore so existing claims reflect the change right away.
    await rescore_all(session, similarity=similarity, decoder=decoder)

    rows = await list_rules_config(session)
    return next(r for r in rows if r.code == code)
