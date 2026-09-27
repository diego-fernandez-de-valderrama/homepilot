"""Test doubles: no network, no Gemini."""

import hashlib
from dataclasses import dataclass, field
from typing import Any

from catalog_ingestion.core import Hashing
from catalog_ingestion.database import UpsertOutcome
from catalog_ingestion.enrichment import LLMResult, PromptBuilder
from catalog_ingestion.models import (
    CatalogProductMapper,
    CatalogProductSchema,
    EnrichedProduct,
    LLMEnrichment,
    LLMEnrichmentMapper,
    LLMEnrichmentSchema,
    ProductState,
    RawProduct,
    RetrievalDocument,
    WebPage,
)


def empty_llm(**overrides: Any) -> LLMEnrichment:
    values: dict[str, Any] = {
        "category": None,
        "product_type": None,
        "brand": None,
        "summary_en": None,
        "summary_de": None,
        "key_features": (),
        "use_cases": (),
        "specs": (),
        "compatibility_claims": (),
        "requirement_claims": (),
    }
    values.update(overrides)
    return LLMEnrichment(**values)


class FakeEmbedder:
    def __init__(self, dimension: int = 8, model: str = "fake-embedding") -> None:
        self._dimension = dimension
        self._model = model
        self.embedded_texts: list[str] = []

    @property
    def model_id(self) -> str:
        return f"{self._model}@{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [byte / 255 + 0.01 for byte in digest[: self._dimension]]

    def embed_documents(self, texts):
        self.embedded_texts.extend(texts)
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakeEnricher:
    """Returns a fixed, schema-valid LLM answer and counts calls."""

    model = "fake-gemini"

    def __init__(self) -> None:
        self.calls = 0

    def enrich(self, product, facts, requirements, web_page) -> LLMResult:
        self.calls += 1
        schema = LLMEnrichmentSchema.model_validate(
            {
                "category": None,
                "product_type": "Smart home device",
                "brand": None,
                "summary_en": f"{product.title}.",
                "summary_de": f"{product.title}.",
                "key_features": ["Feature"],
                "use_cases": ["Home automation"],
                "specs": [],
                "compatibility_claims": [],
                "requirements": [],
            }
        )
        return LLMResult(
            LLMEnrichmentMapper.from_schema(schema), schema.model_dump(mode="json"), self.model, PromptBuilder.VERSION
        )


@dataclass
class InMemoryPostgres:
    """Implements the PostgresRepository methods the pipeline uses."""

    products: dict[str, dict[str, Any]] = field(default_factory=dict)
    web_pages: dict[str, WebPage] = field(default_factory=dict)
    documents: dict[str, RetrievalDocument] = field(default_factory=dict)
    runs: list[dict[str, Any]] = field(default_factory=list)
    cleared_indexed: list[str] = field(default_factory=list)

    def load_states(self) -> dict[str, ProductState]:
        return {
            pid: ProductState(
                row["raw_hash"],
                row["document_hash"],
                row["enrichment_hash"],
                row["llm_output"],
                row.get("enrichment_model"),
                row.get("prompt_version"),
                row["active"],
            )
            for pid, row in self.products.items()
        }

    def load_web_pages(self) -> dict[str, WebPage]:
        return dict(self.web_pages)

    def save_web_page(self, product_id: str, page: WebPage) -> None:
        self.web_pages[page.url] = page

    def upsert_product(self, enriched: EnrichedProduct, raw: RawProduct, raw_hash, enrichment_hash, llm_output):
        document = CatalogProductMapper.to_schema(enriched).model_dump(mode="json")
        document_hash = Hashing.sha256_json(document)
        existing = self.products.get(enriched.id)
        row = {
            "raw_hash": raw_hash,
            "document_hash": document_hash,
            "enrichment_hash": enrichment_hash,
            "llm_output": llm_output,
            "enrichment_model": enriched.enrichment_model,
            "prompt_version": enriched.prompt_version,
            "document": document,
            "active": True,
        }
        if existing is not None and all(
            existing[k] == row[k] for k in ("raw_hash", "document_hash", "enrichment_hash", "active")
        ):
            return UpsertOutcome.UNCHANGED
        self.products[enriched.id] = row
        return UpsertOutcome.INSERTED if existing is None else UpsertOutcome.UPDATED

    def deactivate_missing(self, present_ids) -> list[str]:
        present = set(present_ids)
        if not present:
            return []
        gone = [pid for pid, row in self.products.items() if row["active"] and pid not in present]
        for pid in gone:
            self.products[pid]["active"] = False
        return gone

    def inactive_ids(self) -> list[str]:
        return sorted(pid for pid, row in self.products.items() if not row["active"])

    def clear_indexed(self, product_ids) -> None:
        self.cleared_indexed.extend(product_ids)

    def load_enriched(self, product_ids=None) -> list[EnrichedProduct]:
        return [
            CatalogProductMapper.from_schema(CatalogProductSchema.model_validate(row["document"]))
            for pid, row in sorted(self.products.items())
            if row["active"] and (product_ids is None or pid in product_ids)
        ]

    def save_document(self, document: RetrievalDocument) -> None:
        self.documents[document.product_id] = document

    def mark_indexed(self, documents, embedding_model) -> None:
        pass

    def start_run(self, args) -> int:
        self.runs.append({"args": args})
        return len(self.runs)

    def finish_run(self, run_id, status, stats) -> None:
        self.runs[run_id - 1].update(status=status, stats=stats)
