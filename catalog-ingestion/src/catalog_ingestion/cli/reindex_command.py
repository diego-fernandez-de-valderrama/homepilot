from typing import Annotated

import typer

from catalog_ingestion.cli._counts_printer import CountsPrinter
from catalog_ingestion.cli._resources import CliResources
from catalog_ingestion.cli.rich_progress import RichProgress
from catalog_ingestion.core import AppSettings, LogSetup
from catalog_ingestion.indexing import GeminiEmbedder, QdrantCollection, QdrantRepository
from catalog_ingestion.pipeline import IngestionPipeline


class ReindexCommand:
    @staticmethod
    def run(
        force: Annotated[bool, typer.Option(help="Re-embed every product even if unchanged.")] = False,
        recreate: Annotated[bool, typer.Option(help="Drop and recreate the Qdrant collection first.")] = False,
    ) -> None:
        """Rebuild retrieval documents and embeddings from PostgreSQL (no web, no LLM calls)."""
        LogSetup.configure()
        settings = AppSettings.current()
        gemini = CliResources.gemini(settings)
        if gemini is None:
            raise typer.Exit(code=1)
        client = QdrantCollection.create_client(settings.qdrant)
        name, dimension = settings.qdrant.collection, settings.gemini.embedding_dim
        if not recreate:
            QdrantCollection.ensure(client, name, dimension)
        with CliResources.postgres(settings) as postgres, RichProgress() as progress:
            pipeline = IngestionPipeline(
                postgres=postgres,
                qdrant=QdrantRepository(client, name),
                embedder=GeminiEmbedder(gemini, settings.gemini),
                web=None,
                enricher=None,
                model_name=settings.gemini.model,
                progress=progress,
            )
            # --recreate embeds everything first and only then drops and recreates the collection.
            recreate_collection = (
                (lambda: QdrantCollection.ensure(client, name, dimension, recreate=True)) if recreate else None
            )
            stats = pipeline.reindex(force=force, recreate=recreate_collection)
        CountsPrinter.print("Reindex summary", stats.as_dict())
