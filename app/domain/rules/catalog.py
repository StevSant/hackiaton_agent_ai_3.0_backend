"""Rule catalog — imports all 22 rules and provides lookup functions.

Import order: FS-01..FS-15, then RF-01..RF-07.
The ``all_rules()`` return order determines evaluation order in score_claim.
"""

from __future__ import annotations

from app.domain.rules.hard.RF_01_total_loss_theft import RF01TotalLossTheft
from app.domain.rules.hard.RF_02_document_falsification import RF02DocumentFalsification
from app.domain.rules.hard.RF_03_restrictive_list_match import RF03RestrictiveListMatch
from app.domain.rules.hard.RF_04_impossible_dynamics import RF04ImpossibleDynamics
from app.domain.rules.hard.RF_05_extreme_claim_near_policy_edge import (
    RF05ExtremeClaimNearPolicyEdge,
)
from app.domain.rules.hard.RF_06_atypical_theft_delay import RF06AtypicalTheftDelay
from app.domain.rules.hard.RF_07_cloned_narrative import RF07ClonedNarrative
from app.domain.rules.ports import FraudRule, RuleMeta
from app.domain.rules.signals.FS_01_claim_near_policy_boundary import FS01ClaimNearPolicyBoundary
from app.domain.rules.signals.FS_02_theft_denouncement_delay import FS02TheftDenouncementDelay
from app.domain.rules.signals.FS_03_high_frequency_insured import FS03HighFrequencyInsured
from app.domain.rules.signals.FS_04_high_frequency_vehicle import FS04HighFrequencyVehicle
from app.domain.rules.signals.FS_05_high_frequency_driver import FS05HighFrequencyDriver
from app.domain.rules.signals.FS_06_high_frequency_rc_events import FS06HighFrequencyRCEvents
from app.domain.rules.signals.FS_07_recurrent_provider import FS07RecurrentProvider
from app.domain.rules.signals.FS_08_incomplete_documents import FS08IncompleteDocuments
from app.domain.rules.signals.FS_09_suspicious_dynamics import FS09SuspiciousDynamics
from app.domain.rules.signals.FS_10_severe_damage_no_third_party import FS10SevereDamageNoThirdParty
from app.domain.rules.signals.FS_11_inconsistent_documents import FS11InconsistentDocuments
from app.domain.rules.signals.FS_12_late_report import FS12LateReport
from app.domain.rules.signals.FS_13_similar_narratives import FS13SimilarNarratives
from app.domain.rules.signals.FS_14_amount_near_sum_insured import FS14AmountNearSumInsured
from app.domain.rules.signals.FS_15_vehicle_data_mismatch import FS15VehicleDataMismatch

# Ordered list of all rule instances (signals first, then hard rules)
_ALL_RULES: list[FraudRule] = [
    FS01ClaimNearPolicyBoundary(),
    FS02TheftDenouncementDelay(),
    FS03HighFrequencyInsured(),
    FS04HighFrequencyVehicle(),
    FS05HighFrequencyDriver(),
    FS06HighFrequencyRCEvents(),
    FS07RecurrentProvider(),
    FS08IncompleteDocuments(),
    FS09SuspiciousDynamics(),
    FS10SevereDamageNoThirdParty(),
    FS11InconsistentDocuments(),
    FS12LateReport(),
    FS13SimilarNarratives(),
    FS14AmountNearSumInsured(),
    FS15VehicleDataMismatch(),
    RF01TotalLossTheft(),
    RF02DocumentFalsification(),
    RF03RestrictiveListMatch(),
    RF04ImpossibleDynamics(),
    RF05ExtremeClaimNearPolicyEdge(),
    RF06AtypicalTheftDelay(),
    RF07ClonedNarrative(),
]

_META_BY_CODE: dict[str, RuleMeta] = {r.META.code: r.META for r in _ALL_RULES}


def all_rules() -> list[FraudRule]:
    """Return all 22 rule instances in evaluation order."""
    return list(_ALL_RULES)


def all_meta() -> list[RuleMeta]:
    """Return metadata for all 22 rules (for the catalog endpoint)."""
    return [r.META for r in _ALL_RULES]


def get_meta(code: str) -> RuleMeta | None:
    """Return metadata for a rule by code, or None if not found."""
    return _META_BY_CODE.get(code)
