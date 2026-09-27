"""Composition root: builds the infrastructure clients, repositories and services once."""

import logging
from dataclasses import dataclass

from catalog_ingestion.llm.client import GeminiClient
from catalog_ingestion.retrieval.embeddings import GeminiEmbedder
from catalog_ingestion.storage.postgres.engine import create_session_factory
from catalog_ingestion.storage.qdrant.collection import create_client

from smart_home_agent.config import AgentSettings, Settings
from smart_home_agent.guardrail.classifier import GuardrailThresholds, SemanticGuardrail, gemini_embed
from smart_home_agent.memory.database import create_memory_engine
from smart_home_agent.repositories.postgres import CatalogReader, CatalogRepository, create_readonly_sessions
from smart_home_agent.repositories.profile import ProfileRepository, ProfileStore
from smart_home_agent.repositories.qdrant import QdrantIndex, SemanticIndex
from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.cart import CartService
from smart_home_agent.services.comparison import ComparisonService
from smart_home_agent.services.compatibility import CompatibilityService
from smart_home_agent.services.evidence import EvidenceService
from smart_home_agent.services.profile import ProfileService
from smart_home_agent.services.recommendation import RecommendationService
from smart_home_agent.services.retrieval import RetrievalService
from smart_home_agent.services.rich_content import RichContentService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Services:
    catalog: CatalogReader
    retrieval: RetrievalService
    compatibility: CompatibilityService
    recommendation: RecommendationService
    comparison: ComparisonService
    evidence: EvidenceService
    rich_content: RichContentService
    cart: CartService
    profile: ProfileService | None = None  # None when AGENT_MEMORY_ENABLED=false

    @classmethod
    def create(
        cls,
        catalog: CatalogReader,
        index: SemanticIndex,
        settings: AgentSettings,
        profiles: ProfileStore | None = None,
    ) -> "Services":
        retrieval = RetrievalService(catalog, index)
        accessories = AccessoryService(catalog)  # shared, so the hub products are loaded once
        return cls(
            catalog=catalog,
            retrieval=retrieval,
            compatibility=CompatibilityService(catalog, accessories),
            recommendation=RecommendationService(
                retrieval, accessories, catalog, settings.candidate_pool, settings.upsell_min_relevance
            ),
            comparison=ComparisonService(catalog),
            evidence=EvidenceService(catalog),
            rich_content=RichContentService(catalog),
            cart=CartService(catalog),
            profile=ProfileService(profiles) if profiles is not None else None,
        )


@dataclass(frozen=True, slots=True)
class Container:
    services: Services
    catalog: CatalogRepository
    index: QdrantIndex
    guardrail: SemanticGuardrail | None = None  # None when AGENT_GUARDRAIL_ENABLED=false


def guardrail_thresholds(settings: AgentSettings) -> GuardrailThresholds:
    return GuardrailThresholds(
        smart_home=settings.guardrail_threshold_smart_home,
        electrical=settings.guardrail_threshold_electrical,
        off_topic=settings.guardrail_threshold_off_topic,
        prompt_injection=settings.guardrail_threshold_prompt_injection,
        margin=settings.guardrail_margin,
        off_topic_margin=settings.guardrail_off_topic_margin,
        off_topic_min_words=settings.guardrail_off_topic_min_words,
        block_off_topic=settings.guardrail_input_off_topic,
    )


def build_profile_store(settings: Settings) -> ProfileRepository | None:
    """The customer memory store (None when AGENT_MEMORY_ENABLED=false). No network call until first used.
    Writable, in its own database: the catalog engine stays read-only."""
    if not settings.agent.memory_enabled:
        return None
    return ProfileRepository(create_session_factory(create_memory_engine(settings.postgres, settings.agent.memory_db)))


def build_container(settings: Settings) -> Container:
    _, sessions = create_readonly_sessions(settings.postgres)
    catalog = CatalogRepository(sessions)
    gemini = GeminiClient(settings.gemini)
    embedder = GeminiEmbedder(gemini, settings.gemini)
    index = QdrantIndex(create_client(settings.qdrant), settings.qdrant.collection, embedder)
    mismatched = index.points_with_other_model()
    if mismatched:
        logger.warning(
            "%d Qdrant vectors were not built with the query model %s; their semantic scores are meaningless. "
            "Align GEMINI_EMBEDDING_MODEL/GEMINI_EMBEDDING_DIM or run `catalog-ingestion reindex`.",
            mismatched,
            index.query_embedding_model,
        )
    profiles = build_profile_store(settings)
    guardrail = None
    if settings.agent.guardrail_enabled:
        # Prototype embeddings are computed once here (startup) and cached in memory. Like every guardrail
        # failure, a failed startup embedding fails open: the agent runs without the input check (the
        # deterministic output check and the prompt's rules stay) instead of not starting at all.
        try:
            guardrail = SemanticGuardrail.create(gemini_embed(gemini), guardrail_thresholds(settings.agent))
        except Exception:
            logger.exception("input guardrail disabled: embedding its prototypes failed")
    return Container(
        services=Services.create(catalog, index, settings.agent, profiles),
        catalog=catalog,
        index=index,
        guardrail=guardrail,
    )
