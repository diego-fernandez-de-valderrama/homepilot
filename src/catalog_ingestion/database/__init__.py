"""PostgreSQL, the source of truth. Import everything from here:

    from catalog_ingestion.database import CatalogDatabase, PostgresRepository, ProductRecord, ...

- `CatalogDatabase`: engine, session factory and Alembic migrations (`migrations/`, applied by `init`/`ingest`).
- `records/`: the SQLAlchemy ORM records (`ProductRecord` with its `CompatibilityRecord`/`RequirementRecord`
  child rows, `WebPageRecord`, `RetrievalDocumentRecord`, `IngestionRunRecord`), also read by the agent.
- `PostgresRepository`: everything the pipeline reads and writes (product state for idempotency, the web page
  cache, product upserts reported as `UpsertOutcome`, retrieval documents, run records, `status`).
  ORM records never leave it: it returns the dataclasses of `catalog_ingestion.models`.
"""

from catalog_ingestion.database.catalog_database import CatalogDatabase
from catalog_ingestion.database.postgres_repository import PostgresRepository
from catalog_ingestion.database.records import (
    Base,
    CompatibilityRecord,
    IngestionRunRecord,
    ProductRecord,
    RequirementRecord,
    RetrievalDocumentRecord,
    WebPageRecord,
)
from catalog_ingestion.database.upsert_outcome import UpsertOutcome

__all__ = [
    "Base",
    "CatalogDatabase",
    "CompatibilityRecord",
    "IngestionRunRecord",
    "PostgresRepository",
    "ProductRecord",
    "RequirementRecord",
    "RetrievalDocumentRecord",
    "UpsertOutcome",
    "WebPageRecord",
]
