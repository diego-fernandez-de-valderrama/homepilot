"""In-memory stand-ins for the repositories and product builders (no database, Qdrant or Gemini)."""

from collections.abc import Sequence
from typing import Any

from catalog_ingestion.domain.enums import Dimension, FactSource, FactStatus, Method, Necessity, RequirementKind
from catalog_ingestion.vocabulary.compatibility import term_by_canonical

from smart_home_agent.config import AgentSettings
from smart_home_agent.container import Services
from smart_home_agent.models.evidence import Evidence, FieldProvenance
from smart_home_agent.models.product import CompatibilityFact, Product, ProductRequirement, Spec
from smart_home_agent.models.search import ProductFilter, SearchCandidate
from smart_home_agent.services.filtering import rejection_reason


def evidence(text: str = "catalog text", source: FactSource = FactSource.CATALOG) -> Evidence:
    return Evidence(source=source, text=text, field="attributes.Unterstützte Systeme", method=Method.DETERMINISTIC)


def fact(canonical: str | None, status: FactStatus = FactStatus.SUPPORTED, raw: str | None = None) -> CompatibilityFact:
    term = term_by_canonical(canonical)
    return CompatibilityFact(
        dimension=term.dimension if term else Dimension.ECOSYSTEM,
        canonical_value=canonical,
        label=term.label if term else None,
        raw_value=raw or (term.label if term else "unknown value"),
        status=status,
        evidence=evidence(f"evidence for {raw or canonical}"),
    )


def requirement(
    canonical: str,
    kind: RequirementKind = RequirementKind.HUB,
    alternatives: Sequence[str] = (),
    necessity: Necessity = Necessity.REQUIRED,
) -> ProductRequirement:
    return ProductRequirement(
        item=canonical,
        canonical_item=canonical,
        label=canonical.replace("_", " ").title(),
        kind=kind,
        necessity=necessity,
        alternatives=list(alternatives) or [canonical],
        evidence=evidence("Hinweise: requires a hub"),
    )


def product(
    product_id: str,
    *,
    title: str | None = None,
    category: str | None = "heating_control",
    product_type: str | None = "Radiator thermostat",
    price: float | None = 50.0,
    brand: str | None = "Acme",
    facts: Sequence[CompatibilityFact] = (),
    requirements: Sequence[ProductRequirement] = (),
    specs: Sequence[Spec] = (),
    completeness: float = 1.0,
    **extra: Any,
) -> Product:
    return Product(
        id=product_id,
        title=title or f"Product {product_id}",
        brand=brand,
        category=category,
        category_label_en="Heating control and thermostat" if category == "heating_control" else category,
        category_label_de=None,
        product_type=product_type,
        price=price,
        currency="EUR" if price is not None else None,
        original_price=None,
        summary_en="English summary",
        summary_de="Deutsche Zusammenfassung",
        source_url=None,
        price_raw=f"{price} €" if price is not None else "",
        ean=None,
        image_url=None,
        is_smart_home=True,
        completeness_level="rich",
        completeness_score=completeness,
        key_features=["feature"],
        use_cases=[],
        specs=list(specs),
        compatibility=list(facts),
        requirements=list(requirements),
        attributes={"Technische Daten": {"Schutzart": "IP20"}},
        provenance=[FieldProvenance(field="summary_en", source=FactSource.LLM, method=Method.LLM, confidence=0.6)],
        validation_notes=[],
        **extra,
    )


class FakeCatalog:
    def __init__(self, products: Sequence[Product]) -> None:
        self.products = {p.id: p for p in products}

    def get_products(self, product_ids: Sequence[str]) -> list[Product]:
        return [self.products[pid] for pid in dict.fromkeys(product_ids) if pid in self.products]

    def get_product(self, product_id: str) -> Product | None:
        return self.products.get(product_id)

    def filter_products(self, criteria: ProductFilter) -> tuple[int, list[Product]]:
        matches = [
            p
            for p in self.products.values()
            if rejection_reason(p, criteria) is None
            and all(c in p.supported_values(tuple(Dimension)) for c in criteria.supports)
            and (criteria.product_ids is None or p.id in criteria.product_ids)
        ]
        return len(matches), matches[: criteria.limit]


class FakeIndex:
    """Semantic index with fixed scores; `hidden` ids are only reachable through `score()` (not in top-K)."""

    def __init__(self, scores: dict[str, float], hidden: Sequence[str] = ()) -> None:
        self.scores = scores
        self.hidden = set(hidden)
        self.embedded: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.embedded.append(text)
        return [1.0]

    def search(self, vector: list[float], category: str | None, limit: int) -> list[SearchCandidate]:
        ranked = sorted((pid for pid in self.scores if pid not in self.hidden), key=lambda p: -self.scores[p])
        return [SearchCandidate(pid, self.scores[pid], "semantic") for pid in ranked[:limit]]

    def score(self, vector: list[float], product_ids: Sequence[str]) -> dict[str, float]:
        return {pid: self.scores[pid] for pid in product_ids if pid in self.scores}


def services_for(products: Sequence[Product], scores: dict[str, float] | None = None, **settings: Any) -> Services:
    index = FakeIndex(scores if scores is not None else {p.id: 0.8 for p in products})
    return Services.create(FakeCatalog(products), index, AgentSettings(**settings))  # type: ignore[arg-type]


class FakeToolContext:
    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state: dict[str, Any] = state if state is not None else {}
