from catalog_ingestion.cli._console import CONSOLE
from catalog_ingestion.cli._resources import CliResources
from catalog_ingestion.core import AppSettings, LogSetup


class InitCommand:
    @staticmethod
    def run() -> None:
        """Apply PostgreSQL migrations (Alembic) and create the Qdrant collection (idempotent)."""
        LogSetup.configure()
        settings = AppSettings.current()
        with CliResources.postgres(settings, migrate=True):
            pass
        CliResources.qdrant(settings)
        CONSOLE.print(
            f"[green]Ready[/]: PostgreSQL migrated to head, Qdrant collection '{settings.qdrant.collection}' "
            f"(dim={settings.gemini.embedding_dim})."
        )
