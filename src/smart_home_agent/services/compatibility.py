"""Deterministic compatibility decisions from the structured facts in PostgreSQL.

Rules:
  * a `supported` fact for the canonical value (and no `unsupported` one) -> supported;
  * only `unsupported` facts -> unsupported;
  * contradicting facts -> unknown (with a note);
  * no fact at all -> unknown. Missing information is never turned into supported or unsupported.
Related concepts (Siri vs HomeKit, Google Assistant vs Google Home) only produce notes.
"""

from collections.abc import Sequence

from catalog_ingestion.domain.enums import FactStatus, Necessity, RequirementKind
from catalog_ingestion.vocabulary.compatibility import surface_forms

from smart_home_agent.models.compatibility import CompatibilityResult, RequirementCheck, RequirementStatus, TermCheck
from smart_home_agent.models.product import Product, ProductRequirement
from smart_home_agent.repositories.postgres import CatalogReader
from smart_home_agent.services import vocabulary
from smart_home_agent.services.accessories import AccessoryService
from smart_home_agent.services.vocabulary import ResolvedTerm

_DEVICE_KINDS = (RequirementKind.HUB, RequirementKind.GATEWAY)


class ProductNotFoundError(LookupError):
    def __init__(self, product_ids: Sequence[str]) -> None:
        self.product_ids = list(product_ids)
        super().__init__(f"product(s) not found in the catalog: {', '.join(self.product_ids)}")


def term_status(product: Product, canonical: str) -> tuple[FactStatus, list[str]]:
    """Status of one canonical value for one product, plus explanatory notes."""
    facts = product.facts_for(canonical)
    statuses = {fact.status for fact in facts}
    if FactStatus.SUPPORTED in statuses and FactStatus.UNSUPPORTED in statuses:
        return FactStatus.UNKNOWN, ["The catalog contains contradicting evidence for this value."]
    if FactStatus.SUPPORTED in statuses:
        return FactStatus.SUPPORTED, []
    if FactStatus.UNSUPPORTED in statuses:
        return FactStatus.UNSUPPORTED, []
    return FactStatus.UNKNOWN, ["The catalog has no information about this value."]


def _related_notes(product: Product, resolved: ResolvedTerm) -> list[str]:
    supported = product.supported_values()
    return [
        f"The product supports {vocabulary.label(related)}, which is a different concept and does not "
        f"confirm {resolved.label}."
        for related in vocabulary.RELATED_NOT_EQUIVALENT.get(resolved.canonical, ())
        if related in supported
    ]


def _unmapped_mentions(product: Product, resolved: ResolvedTerm) -> list[str]:
    forms = surface_forms(resolved.canonical)
    return [
        f"Unmapped catalog mention {fact.raw_value!r} may refer to {resolved.label}; it is not a confirmation."
        for fact in product.compatibility
        if fact.canonical_value is None and any(form in fact.raw_value.casefold() for form in forms)
    ]


def check_term(product: Product, resolved: ResolvedTerm) -> TermCheck:
    status, notes = term_status(product, resolved.canonical)
    if status is FactStatus.UNKNOWN:
        notes = notes + _related_notes(product, resolved) + _unmapped_mentions(product, resolved)
    return TermCheck(
        term=resolved.canonical,
        label=resolved.label,
        dimension=resolved.dimension,
        status=status,
        evidence=[fact.evidence for fact in product.facts_for(resolved.canonical)],
        notes=notes,
    )


def check_requirement(requirement: ProductRequirement, owned_devices: Sequence[str] | None) -> RequirementCheck:
    status: RequirementStatus = "info"
    if requirement.kind in _DEVICE_KINDS and requirement.necessity is Necessity.REQUIRED:
        options = set(requirement.alternatives) | (
            {requirement.canonical_item} if requirement.canonical_item else set()
        )
        if "standalone" in options or (owned_devices and options & set(owned_devices)):
            status = "satisfied"
        elif owned_devices is None:
            status = "unverified"
        else:
            status = "missing"
    return RequirementCheck(
        label=requirement.label,
        canonical_item=requirement.canonical_item,
        kind=requirement.kind,
        necessity=requirement.necessity,
        alternatives=[vocabulary.requirement_label(a) for a in requirement.alternatives],
        status=status,
        evidence=requirement.evidence,
    )


def overall_status(checks: Sequence[TermCheck]) -> FactStatus:
    statuses = {check.status for check in checks}
    if FactStatus.UNSUPPORTED in statuses:
        return FactStatus.UNSUPPORTED
    if statuses <= {FactStatus.SUPPORTED}:
        return FactStatus.SUPPORTED
    return FactStatus.UNKNOWN


def evaluate(
    product: Product, terms: Sequence[ResolvedTerm], owned_devices: Sequence[str] | None = None
) -> CompatibilityResult:
    checks = [check_term(product, t) for t in terms]
    return CompatibilityResult(
        product_id=product.id,
        title=product.title,
        overall=overall_status(checks),
        checks=checks,
        requirements=[check_requirement(r, owned_devices) for r in product.requirements],
        requires_professional_installation=product.requires_professional_installation,
    )


class CompatibilityService:
    def __init__(self, catalog: CatalogReader, accessories: AccessoryService | None = None) -> None:
        self._catalog = catalog
        self._accessories = accessories

    def check(
        self, product_ids: Sequence[str], terms: Sequence[ResolvedTerm], owned_devices: Sequence[str] | None = None
    ) -> list[CompatibilityResult]:
        products = self._catalog.get_products(product_ids)
        missing = [pid for pid in product_ids if pid not in {p.id for p in products}]
        if missing:
            raise ProductNotFoundError(missing)
        results = []
        for product in products:
            result = evaluate(product, terms, owned_devices)
            if self._accessories:  # the catalog hub products for required hubs the customer may not own
                result.accessories = self._accessories.for_product(product, result.requirements)
            results.append(result)
        return results
