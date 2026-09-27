"""In-memory stand-ins for the repositories and product builders (no database, Qdrant or Gemini)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from catalog_ingestion.domain.enums import Dimension, FactSource, FactStatus, Method, Necessity, RequirementKind
from catalog_ingestion.vocabulary.compatibility import term_by_canonical
from google.genai import types

from smart_home_agent.config import AgentSettings
from smart_home_agent.container import Services
from smart_home_agent.models import (
    CompatibilityFact,
    CustomerFact,
    CustomerProfile,
    CustomerSummary,
    Evidence,
    FieldProvenance,
    NewFact,
    Product,
    ProductFilter,
    ProductRequirement,
    SearchCandidate,
    Spec,
)
from smart_home_agent.services import HardFilter


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

    def get_versions(self, titles: Sequence[str]) -> dict[str, list[Product]]:
        versions: dict[str, list[Product]] = {}
        for p in sorted(self.products.values(), key=lambda p: (p.price is None, p.price or 0.0, p.id)):
            if p.title in titles:
                versions.setdefault(p.title, []).append(p)
        return versions

    def filter_products(self, criteria: ProductFilter) -> tuple[int, list[Product]]:
        """Same semantics as the SQL in CatalogRepository: product_type_contains (type or title, case-insensitive)
        and the sort order included, so tests of those parameters actually test something."""
        needle = (criteria.product_type_contains or "").strip().casefold()
        matches = [
            p
            for p in self.products.values()
            if HardFilter.rejection_reason(p, criteria) is None
            and all(c in p.supported_values(tuple(Dimension)) for c in criteria.supports)
            and (criteria.product_ids is None or p.id in criteria.product_ids)
            and (not needle or needle in (p.product_type or "").casefold() or needle in p.title.casefold())
        ]
        match criteria.sort:
            case "price_asc":
                matches.sort(key=lambda p: (p.price is None, p.price or 0.0, p.id))
            case "price_desc":
                matches.sort(key=lambda p: (p.price is None, -(p.price or 0.0), p.id))
            case _:
                matches.sort(key=lambda p: (-p.completeness_score, p.id))
        return len(matches), matches[: criteria.limit]


class FakeIndex:
    """Semantic index with fixed scores; `hidden` ids are only reachable through `score()` (not in top-K)."""

    def __init__(
        self, scores: dict[str, float], hidden: Sequence[str] = (), categories: dict[str, str | None] | None = None
    ) -> None:
        self.scores = scores
        self.hidden = set(hidden)
        self.categories = categories or {}  # product id -> category, for the category pre-filter
        self.embedded: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.embedded.append(text)
        return [1.0]

    def search(self, vector: list[float], category: str | None, limit: int) -> list[SearchCandidate]:
        """Like the Qdrant pre-filter: with a category, only products of that category (when `categories` knows
        them) are returned."""
        ranked = sorted(
            (
                pid
                for pid in self.scores
                if pid not in self.hidden
                and (category is None or pid not in self.categories or self.categories[pid] == category)
            ),
            key=lambda p: -self.scores[p],
        )
        return [SearchCandidate(pid, self.scores[pid], "semantic") for pid in ranked[:limit]]

    def score(self, vector: list[float], product_ids: Sequence[str]) -> dict[str, float]:
        return {pid: self.scores[pid] for pid in product_ids if pid in self.scores}


class FakeProfileStore:
    """Customer memory in a list, with the same semantics as ProfileRepository."""

    def __init__(self) -> None:
        self.facts: list[CustomerFact] = []
        self.fail = False  # True: every call raises, like an unreachable database

    def load(self, user_id: str, include_retracted: bool = False) -> CustomerProfile:
        if self.fail:
            raise ConnectionError("memory database down")
        facts = [f for f in self.facts if f.user_id == user_id and (include_retracted or f.active)]
        return CustomerProfile(user_id=user_id, facts=[f.model_copy() for f in facts])

    def customers(self) -> list[CustomerSummary]:
        if self.fail:
            raise ConnectionError("memory database down")
        users = dict.fromkeys(f.user_id for f in sorted(self.facts, key=lambda f: f.created_at, reverse=True))
        summaries = []
        for user in users:
            facts = [f for f in self.facts if f.user_id == user]
            last = max(max(f.created_at, f.retracted_at or f.created_at) for f in facts)
            active = sum(f.active for f in facts)
            summaries.append(
                CustomerSummary(user_id=user, active_facts=active, total_facts=len(facts), last_activity=last)
            )
        return sorted(summaries, key=lambda s: s.last_activity, reverse=True)

    def apply(
        self,
        user_id: str,
        session_id: str | None,
        evidence: str,
        add: Sequence[NewFact],
        retract_ids: Sequence[int],
    ) -> tuple[list[CustomerFact], list[CustomerFact]]:
        now = datetime.now(UTC)
        remaining = [
            (f.kind, f.value) for f in self.facts if f.user_id == user_id and f.active and f.id not in retract_ids
        ]
        for fact in add:  # the partial unique index customer_facts_active_value_key
            if (fact.kind, fact.value) in remaining:
                raise ValueError(f"duplicate active fact {fact.kind}={fact.value} (unique index)")
            remaining.append((fact.kind, fact.value))
        retracted = []
        for index, stored in enumerate(self.facts):
            if stored.user_id == user_id and stored.id in retract_ids and stored.active:
                self.facts[index] = stored.model_copy(
                    update={"active": False, "retracted_at": now, "retracted_evidence": evidence}
                )
                retracted.append(self.facts[index])
        added = [
            CustomerFact(
                id=len(self.facts) + i + 1,
                user_id=user_id,
                session_id=session_id,
                evidence=evidence,
                created_at=now,
                **fact.model_dump(),
            )
            for i, fact in enumerate(add)
        ]
        self.facts += added
        return added, retracted


def services_for(
    products: Sequence[Product],
    scores: dict[str, float] | None = None,
    profiles: FakeProfileStore | None = None,
    **settings: Any,
) -> Services:
    index = FakeIndex(
        scores if scores is not None else {p.id: 0.8 for p in products}, categories={p.id: p.category for p in products}
    )
    return Services.create(FakeCatalog(products), index, AgentSettings(**settings), profiles)


class FakeToolContext:
    def __init__(
        self, state: dict[str, Any] | None = None, message: str | None = None, user_id: str = "customer"
    ) -> None:
        self.state: dict[str, Any] = state if state is not None else {}
        self.user_id = user_id
        self.session = SimpleNamespace(id="session-1")
        self.user_content = types.Content(role="user", parts=[types.Part(text=message)]) if message else None
