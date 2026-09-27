"""Shared infrastructure, used by every other package (and by the agent). Import everything from here:

    from catalog_ingestion.core import AppSettings, GeminiClient, Hashing, LogSetup, ...

- `settings/`: `AppSettings` and one settings class per env prefix (`GeminiSettings`, `PostgresSettings`,
  `QdrantSettings`, `WebSettings`, `IngestSettings`).
- `gemini/`: `GeminiClient` (pacing, retries, quota errors) and the `TextGenerator` protocol.
- `LogSetup`: key=value logging on stderr (`LogSetup.fields(...)` for structured `extra`).
- `Hashing`: stable content hashes that decide which pipeline stages must re-run.
"""

from catalog_ingestion.core.gemini import (
    GeminiCancelledError,
    GeminiClient,
    GeminiModelNotFoundError,
    GeminiNotConfiguredError,
    QuotaExhaustedError,
    TextGenerator,
)
from catalog_ingestion.core.hashing import Hashing
from catalog_ingestion.core.log_setup import LogSetup
from catalog_ingestion.core.settings import (
    AppSettings,
    GeminiSettings,
    IngestSettings,
    PostgresSettings,
    QdrantSettings,
    WebSettings,
)

__all__ = [
    "AppSettings",
    "GeminiCancelledError",
    "GeminiClient",
    "GeminiModelNotFoundError",
    "GeminiNotConfiguredError",
    "GeminiSettings",
    "Hashing",
    "IngestSettings",
    "LogSetup",
    "PostgresSettings",
    "QdrantSettings",
    "QuotaExhaustedError",
    "TextGenerator",
    "WebSettings",
]
