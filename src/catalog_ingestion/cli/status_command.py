import json

from catalog_ingestion.cli._console import CONSOLE
from catalog_ingestion.cli._counts_printer import CountsPrinter
from catalog_ingestion.cli._resources import CliResources
from catalog_ingestion.core import AppSettings, LogSetup
from catalog_ingestion.indexing import QdrantCollection


class StatusCommand:
    @staticmethod
    def run() -> None:
        """Show catalog counts in PostgreSQL and Qdrant."""
        LogSetup.configure()
        settings = AppSettings.current()
        with CliResources.postgres(settings) as postgres:
            info = postgres.status()
        client = QdrantCollection.create_client(settings.qdrant)
        collection = settings.qdrant.collection
        points = client.count(collection, exact=True).count if client.collection_exists(collection) else 0
        CountsPrinter.print("PostgreSQL products", info["products"])
        CountsPrinter.print("Completeness", info["completeness"], humanize=False)
        CountsPrinter.print("Web status", info["web_status"], humanize=False)
        CountsPrinter.print("Compatibility facts by method", info["compatibility_facts_by_method"], humanize=False)
        CountsPrinter.print("Qdrant", {"collection": collection, "points": points})
        if info["last_run"]:
            CONSOLE.print_json(json.dumps(info["last_run"], default=str))
