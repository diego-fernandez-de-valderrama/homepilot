"""SQLAlchemy ORM records: the PostgreSQL schema.

These are persistence models only. The pipeline works on the frozen dataclasses of
`catalog_ingestion.models`; `PostgresRepository` converts between the two.

Hybrid model:
  * typed columns + child tables for everything the agent filters or joins on
    deterministically (price, category, brand, compatibility, requirements);
  * JSONB for heterogeneous data (302 distinct attribute keys), the full enriched
    document and audit copies (raw input, cached LLM output).

Schema changes go through Alembic: edit these records, then
`uv run alembic revision --autogenerate -m "..."` and review the generated migration.
"""

from catalog_ingestion.database.records.base import Base
from catalog_ingestion.database.records.compatibility_record import CompatibilityRecord
from catalog_ingestion.database.records.ingestion_run_record import IngestionRunRecord
from catalog_ingestion.database.records.product_record import ProductRecord
from catalog_ingestion.database.records.requirement_record import RequirementRecord
from catalog_ingestion.database.records.retrieval_document_record import RetrievalDocumentRecord
from catalog_ingestion.database.records.web_page_record import WebPageRecord

__all__ = [
    "Base",
    "CompatibilityRecord",
    "IngestionRunRecord",
    "ProductRecord",
    "RequirementRecord",
    "RetrievalDocumentRecord",
    "WebPageRecord",
]
