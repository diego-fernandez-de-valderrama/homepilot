import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

from catalog_ingestion.core import AppSettings, GeminiClient
from catalog_ingestion.database import CatalogDatabase, PostgresRepository
from catalog_ingestion.indexing import QdrantCollection, QdrantRepository

logger = logging.getLogger(__name__)

InputOption = Annotated[
    Path | None, typer.Option("--input", "-i", help="Path to products.zip (default: INGEST_INPUT_PATH).")
]


class CliResources:
    """Builds the components the commands inject into the pipeline."""

    @staticmethod
    def gemini(settings: AppSettings) -> GeminiClient | None:
        if not settings.gemini.is_configured:
            logger.warning(
                "GEMINI_API_KEY is not set: LLM enrichment, url_context fetching and embeddings are disabled"
            )
            return None
        return GeminiClient(settings.gemini)

    @staticmethod
    def qdrant(settings: AppSettings) -> QdrantRepository:
        """The repository of the configured collection, created if missing."""
        client = QdrantCollection.create_client(settings.qdrant)
        QdrantCollection.ensure(client, settings.qdrant.collection, settings.gemini.embedding_dim)
        return QdrantRepository(client, settings.qdrant.collection)

    @staticmethod
    @contextmanager
    def postgres(settings: AppSettings, migrate: bool = False) -> Iterator[PostgresRepository]:
        """Repository bound to a fresh engine; `migrate` applies pending Alembic migrations first."""
        engine = CatalogDatabase.create_engine(settings.postgres)
        try:
            if migrate:
                CatalogDatabase.upgrade_to_head(engine)
            yield PostgresRepository(CatalogDatabase.session_factory(engine))
        finally:
            engine.dispose()

    @staticmethod
    def resolve_input(path: Path | None, settings: AppSettings) -> Path:
        resolved = path or settings.ingest.input_path
        if not resolved.is_file():
            raise typer.BadParameter(f"input file not found: {resolved}", param_hint="--input")
        return resolved
