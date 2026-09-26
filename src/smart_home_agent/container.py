"""Composition root: builds the infrastructure clients, repositories and services once."""

import logging
from dataclasses import dataclass

from catalog_ingestion.llm.client import GeminiClient
from catalog_ingestion.retrieval.embeddings import GeminiEmbedder
from catalog_ingestion.storage.qdrant.collection import create_client

from smart_home_agent.config import AgentSettings, Settings
from smart_home_agent.repositories.postgres import CatalogRepository, create_readonly_sessions
from smart_home_agent.repositories.qdrant import QdrantIndex, SemanticIndex
from smart_home_agent.services.comparison import ComparisonService
from smart_home_agent.services.compatibility import CompatibilityService
from smart_home_agent.services.evidence import EvidenceService
from smart_home_agent.services.recommendation import RecommendationService
from smart_home_agent.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Services:
    catalog: CatalogRepository
    retrieval: RetrievalService
    compatibility: CompatibilityService
    recommendation: RecommendationService
    comparison: ComparisonService
    evidence: EvidenceService

    @classmethod
    def create(cls, catalog: CatalogRepository, index: SemanticIndex, settings: AgentSettings) -> "Services":
        retrieval = RetrievalService(catalog, index)
        return cls(
            catalog=catalog,
            retrieval=retrieval,
            compatibility=CompatibilityService(catalog),
            recommendation=RecommendationService(retrieval, settings.candidate_pool, settings.upsell_min_relevance),
            comparison=ComparisonService(catalog),
            evidence=EvidenceService(catalog),
        )


@dataclass(frozen=True, slots=True)
class Container:
    services: Services
    catalog: CatalogRepository
    index: QdrantIndex


def build_container(settings: Settings) -> Container:
    _, sessions = create_readonly_sessions(settings.postgres)
    catalog = CatalogRepository(sessions)
    embedder = GeminiEmbedder(GeminiClient(settings.gemini), settings.gemini)
    index = QdrantIndex(create_client(settings.qdrant), settings.qdrant.collection, embedder)
    indexed_model = index.indexed_embedding_model()
    if indexed_model and indexed_model != index.query_embedding_model:
        logger.warning(
            "Qdrant vectors were built with %s but queries use %s; semantic scores will be meaningless. "
            "Align GEMINI_EMBEDDING_MODEL/GEMINI_EMBEDDING_DIM or run `catalog-ingestion reindex`.",
            indexed_model,
            index.query_embedding_model,
        )
    return Container(services=Services.create(catalog, index, settings.agent), catalog=catalog, index=index)
