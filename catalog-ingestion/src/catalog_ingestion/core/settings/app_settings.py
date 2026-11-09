from functools import cache

from pydantic import BaseModel

from catalog_ingestion.core.settings.gemini_settings import GeminiSettings
from catalog_ingestion.core.settings.ingest_settings import IngestSettings
from catalog_ingestion.core.settings.postgres_settings import PostgresSettings
from catalog_ingestion.core.settings.qdrant_settings import QdrantSettings
from catalog_ingestion.core.settings.web_settings import WebSettings


class AppSettings(BaseModel):
    """All settings of one process. The CLI reads them once (`current`) and injects the parts."""

    gemini: GeminiSettings
    postgres: PostgresSettings
    qdrant: QdrantSettings
    web: WebSettings
    ingest: IngestSettings

    @classmethod
    def load(cls) -> "AppSettings":
        """Reads the environment (and `.env`) now."""
        return cls(
            gemini=GeminiSettings(),
            postgres=PostgresSettings(),
            qdrant=QdrantSettings(),
            web=WebSettings(),
            ingest=IngestSettings(),
        )

    @staticmethod
    @cache
    def current() -> "AppSettings":
        """The settings of this process, loaded on first use."""
        return AppSettings.load()
