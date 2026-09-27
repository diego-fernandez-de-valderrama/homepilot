"""Conversions between the domain dataclasses and the boundary schemas. The only place that knows both.

- `RawProductMapper`: `RawProductSchema` -> `RawProduct` (input).
- `LLMEnrichmentMapper`: `LLMEnrichmentSchema` -> `LLMEnrichment` (Gemini output, still unvalidated).
- `NormalizedProductMapper`, `FactMapper`: the parts of a stored product, both directions.
- `CatalogProductMapper`: `EnrichedProduct` <-> `CatalogProductSchema` (`products.document`).
- `QdrantPayloadMapper`: `EnrichedProduct` -> `QdrantPayloadSchema`.
"""

from catalog_ingestion.models.mappers.catalog_product_mapper import CatalogProductMapper
from catalog_ingestion.models.mappers.fact_mapper import FactMapper
from catalog_ingestion.models.mappers.llm_enrichment_mapper import LLMEnrichmentMapper
from catalog_ingestion.models.mappers.normalized_product_mapper import NormalizedProductMapper
from catalog_ingestion.models.mappers.qdrant_payload_mapper import QdrantPayloadMapper
from catalog_ingestion.models.mappers.raw_product_mapper import RawProductMapper

__all__ = [
    "CatalogProductMapper",
    "FactMapper",
    "LLMEnrichmentMapper",
    "NormalizedProductMapper",
    "QdrantPayloadMapper",
    "RawProductMapper",
]
