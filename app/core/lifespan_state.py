"""Lifespan-pinned AI stack — built once at app startup, pinned to `app.state.ai`.

Heavy components (sentence-transformer encoder, LightGBM Booster, IsolationForest)
load once here. Per-request handlers read them from `app.state.ai`. Models that
aren't on disk yet are simply absent — the `/status/ai` endpoint reports which
slots are filled so the team can see at a glance what's wired.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import structlog

from app.core.config import settings
from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier
from app.infrastructure.anomaly import IsolationForestDetector, NearestNormalIndex
from app.infrastructure.embeddings import (
    EmbeddingsProvider,
    SentenceTransformersAdapter,
    build_openai_embeddings_adapter,
)
from app.infrastructure.llm import (
    InMemoryFakeLLM,
    LLMProvider,
    PromptLoader,
    build_openai_adapter,
)
from app.infrastructure.llm.prompt_loader import PromptLoader as _PromptLoader  # noqa: F401
from app.infrastructure.ml import LightGBMClassifier

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class AIState:
    """All AI adapters live here, pinned to `app.state.ai`."""

    llm: LLMProvider
    llm_provider: str
    llm_model: str
    embeddings: EmbeddingsProvider | None
    embeddings_model: str
    embeddings_dim: int
    prompts: PromptLoader
    fraud_classifier: FraudClassifier | None
    fraud_model_present: bool
    anomaly_detector: AnomalyDetector | None
    anomaly_model_present: bool
    nearest_normal_index_present: bool


def _build_llm() -> tuple[LLMProvider, str]:
    """Pick the LLM adapter from settings. Falls back to FakeLLM when no API key."""
    if settings.LLM_PROVIDER == "fake":
        logger.info("ai.llm.fake_selected")
        return InMemoryFakeLLM(), "fake"
    if settings.OPENAI_API_KEY is None:
        logger.warning("ai.llm.no_api_key_falling_back_to_fake")
        return InMemoryFakeLLM(), "fake"
    logger.info("ai.llm.openai_selected", model=settings.LLM_DEFAULT_MODEL)
    return build_openai_adapter(), "openai"


def _build_embeddings() -> EmbeddingsProvider | None:
    """Build the embeddings adapter selected by ``settings.EMBEDDINGS_PROVIDER``.

    Returns None on failure so the app still boots (the agent's 12 NL questions
    don't need embeddings — only FS-13 does).
    """
    try:
        if settings.EMBEDDINGS_PROVIDER == "openai":
            if settings.OPENAI_API_KEY is None:
                logger.warning("ai.embeddings.no_api_key_skipping_openai")
                return None
            adapter: EmbeddingsProvider = build_openai_embeddings_adapter()
        else:
            adapter = SentenceTransformersAdapter(model_name=settings.EMBEDDINGS_MODEL)
        logger.info(
            "ai.embeddings.loaded",
            provider=settings.EMBEDDINGS_PROVIDER,
            model=settings.EMBEDDINGS_MODEL,
            dim=getattr(adapter, "dimension", settings.EMBEDDINGS_DIM),
        )
        return adapter
    except Exception as exc:
        logger.warning("ai.embeddings.load_failed", error=str(exc))
        return None


def _build_fraud_classifier(path: str) -> FraudClassifier | None:
    """Load the LGBM classifier when the artifact is on disk; otherwise None."""
    if not Path(path).is_file():
        logger.info("ai.fraud_classifier.absent", path=path)
        return None
    try:
        classifier = LightGBMClassifier(model_path=path)
        logger.info("ai.fraud_classifier.loaded", path=path)
        return classifier
    except Exception as exc:
        logger.warning("ai.fraud_classifier.load_failed", error=str(exc), path=path)
        return None


def _build_anomaly_detector(
    model_path: str, knn_path: str
) -> AnomalyDetector | None:
    """Load IsolationForest + optional kNN sidecar. kNN absent → no nearest-normal."""
    if not Path(model_path).is_file():
        logger.info("ai.anomaly_detector.absent", path=model_path)
        return None
    try:
        knn: NearestNormalIndex | None = None
        if NearestNormalIndex.file_exists(knn_path):
            try:
                knn = NearestNormalIndex(model_path=knn_path)
                logger.info("ai.nearest_normal.loaded", path=knn_path)
            except Exception as exc:
                logger.warning("ai.nearest_normal.load_failed", error=str(exc), path=knn_path)
                knn = None
        detector = IsolationForestDetector(model_path=model_path, nearest_normal=knn)
        logger.info("ai.anomaly_detector.loaded", path=model_path, knn_loaded=knn is not None)
        return detector
    except Exception as exc:
        logger.warning("ai.anomaly_detector.load_failed", error=str(exc), path=model_path)
        return None


def _build_prompts() -> PromptLoader:
    base = Path(__file__).resolve().parents[1] / "agents" / "claims_agent" / "prompts"
    return PromptLoader(base_dir=base)


def build_lifespan_state() -> AIState:
    """Build the AI stack snapshot. Sync — runs once at app startup."""
    llm, llm_provider = _build_llm()
    embeddings = _build_embeddings()
    fraud_classifier = _build_fraud_classifier(settings.FRAUD_MODEL_PATH)
    anomaly_detector = _build_anomaly_detector(
        settings.ANOMALY_MODEL_PATH, settings.NEAREST_NORMAL_INDEX_PATH
    )
    return AIState(
        llm=llm,
        llm_provider=llm_provider,
        llm_model=settings.LLM_DEFAULT_MODEL,
        embeddings=embeddings,
        embeddings_model=settings.EMBEDDINGS_MODEL,
        embeddings_dim=embeddings.dimension if embeddings else settings.EMBEDDINGS_DIM,
        prompts=_build_prompts(),
        fraud_classifier=fraud_classifier,
        fraud_model_present=fraud_classifier is not None,
        anomaly_detector=anomaly_detector,
        anomaly_model_present=anomaly_detector is not None,
        nearest_normal_index_present=Path(settings.NEAREST_NORMAL_INDEX_PATH).is_file(),
    )
