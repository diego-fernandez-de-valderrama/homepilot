"""Frozen dataclasses the pipeline works on (never Pydantic, never ORM), in flow order:

- input and normalization: `RawProduct` -> `NormalizedProduct` (`Price`, `Description`, `SubtitleParts`,
  `ParsedAttributes` of `AttributeEntry`s);
- facts with provenance: `CompatibilityFact`, `Requirement`, each with its `Evidence`; `CompletenessReport`;
- enrichment input: `WebPage`, `LLMEnrichment` (unvalidated `CompatibilityClaim`s, `RequirementClaim`s, `Spec`s);
- the validated result: `EnrichedProduct` (with `FieldProvenance`);
- stored state: `ProductState` (idempotency hashes, cached LLM output), `RetrievalDocument` (the embedded text).
"""

from catalog_ingestion.models.domain.attribute_entry import AttributeEntry
from catalog_ingestion.models.domain.compatibility_claim import CompatibilityClaim
from catalog_ingestion.models.domain.compatibility_fact import CompatibilityFact
from catalog_ingestion.models.domain.completeness_report import CompletenessReport
from catalog_ingestion.models.domain.description import Description
from catalog_ingestion.models.domain.enriched_product import EnrichedProduct
from catalog_ingestion.models.domain.evidence import Evidence
from catalog_ingestion.models.domain.field_provenance import FieldProvenance
from catalog_ingestion.models.domain.llm_enrichment import LLMEnrichment
from catalog_ingestion.models.domain.normalized_product import NormalizedProduct
from catalog_ingestion.models.domain.parsed_attributes import ParsedAttributes
from catalog_ingestion.models.domain.price import Price
from catalog_ingestion.models.domain.product_state import ProductState
from catalog_ingestion.models.domain.raw_product import RawProduct
from catalog_ingestion.models.domain.requirement import Requirement
from catalog_ingestion.models.domain.requirement_claim import RequirementClaim
from catalog_ingestion.models.domain.retrieval_document import RetrievalDocument
from catalog_ingestion.models.domain.spec import Spec
from catalog_ingestion.models.domain.subtitle_parts import SubtitleParts
from catalog_ingestion.models.domain.web_page import WebPage

__all__ = [
    "AttributeEntry",
    "CompatibilityClaim",
    "CompatibilityFact",
    "CompletenessReport",
    "Description",
    "EnrichedProduct",
    "Evidence",
    "FieldProvenance",
    "LLMEnrichment",
    "NormalizedProduct",
    "ParsedAttributes",
    "Price",
    "ProductState",
    "RawProduct",
    "Requirement",
    "RequirementClaim",
    "RetrievalDocument",
    "Spec",
    "SubtitleParts",
    "WebPage",
]
