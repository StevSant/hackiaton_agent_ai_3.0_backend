"""Import SSE stream event schemas — discriminated union ``ImportStreamEvent``."""

from typing import Annotated

from pydantic import Field

from app.schemas.imports.stream.anomaly_detected_event import (
    AnomalyDetectedData,
    AnomalyDetectedEvent,
)
from app.schemas.imports.stream.case_completed_event import (
    CaseCompletedData,
    CaseCompletedEvent,
)
from app.schemas.imports.stream.case_started_event import (
    CaseStartedData,
    CaseStartedEvent,
)
from app.schemas.imports.stream.import_completed_event import (
    ImportCompletedData,
    ImportCompletedEvent,
)
from app.schemas.imports.stream.import_error_event import (
    ImportErrorData,
    ImportErrorEvent,
)
from app.schemas.imports.stream.import_started_event import (
    ImportStartedData,
    ImportStartedEvent,
)
from app.schemas.imports.stream.ml_scored_event import MLScoredData, MLScoredEvent
from app.schemas.imports.stream.parse_row_event import ParseRowData, ParseRowEvent
from app.schemas.imports.stream.rule_hard_fired_event import (
    RuleHardFiredData,
    RuleHardFiredEvent,
)
from app.schemas.imports.stream.rule_scoring_event import (
    RuleScoringData,
    RuleScoringEvent,
)
from app.schemas.imports.stream.similarity_found_event import (
    SimilarClaimRef,
    SimilarityFoundData,
    SimilarityFoundEvent,
)

ImportStreamEvent = Annotated[
    ImportStartedEvent
    | ParseRowEvent
    | CaseStartedEvent
    | RuleHardFiredEvent
    | RuleScoringEvent
    | MLScoredEvent
    | AnomalyDetectedEvent
    | SimilarityFoundEvent
    | CaseCompletedEvent
    | ImportCompletedEvent
    | ImportErrorEvent,
    Field(discriminator="type"),
]

__all__ = [
    "AnomalyDetectedData",
    "AnomalyDetectedEvent",
    "CaseCompletedData",
    "CaseCompletedEvent",
    "CaseStartedData",
    "CaseStartedEvent",
    "ImportCompletedData",
    "ImportCompletedEvent",
    "ImportErrorData",
    "ImportErrorEvent",
    "ImportStartedData",
    "ImportStartedEvent",
    "ImportStreamEvent",
    "MLScoredData",
    "MLScoredEvent",
    "ParseRowData",
    "ParseRowEvent",
    "RuleHardFiredData",
    "RuleHardFiredEvent",
    "RuleScoringData",
    "RuleScoringEvent",
    "SimilarClaimRef",
    "SimilarityFoundData",
    "SimilarityFoundEvent",
]
