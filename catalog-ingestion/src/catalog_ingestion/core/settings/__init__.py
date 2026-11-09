"""Settings from environment variables and an optional `.env` file (current working directory).

One class per concern, each with its own env prefix: `GeminiSettings` (GEMINI_), `PostgresSettings`
(POSTGRES_), `QdrantSettings` (QDRANT_), `WebSettings` (WEB_), `IngestSettings` (INGEST_). `AppSettings`
composes them; the CLI loads it once (`AppSettings.current()`) and injects the parts by constructor.
"""

from catalog_ingestion.core.settings.app_settings import AppSettings
from catalog_ingestion.core.settings.gemini_settings import GeminiSettings
from catalog_ingestion.core.settings.ingest_settings import IngestSettings
from catalog_ingestion.core.settings.postgres_settings import PostgresSettings
from catalog_ingestion.core.settings.qdrant_settings import QdrantSettings
from catalog_ingestion.core.settings.web_settings import WebSettings

__all__ = [
    "AppSettings",
    "GeminiSettings",
    "IngestSettings",
    "PostgresSettings",
    "QdrantSettings",
    "WebSettings",
]
